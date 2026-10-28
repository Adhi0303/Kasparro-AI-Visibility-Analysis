import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import Dataset, Report, ReportVersion
from app.reports import create_initial_report, submit_report_for_review, edit_draft_report
from app.review import process_review_decision
from app.export import export_approved_report
from app.schemas import ReviewDecisionRequest, DraftReportEditRequest


@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    try:
        ds = Dataset(name="test-ds", source_hash="dummy-hash", validation_status="valid")
        session.add(ds)
        session.commit()
        yield session
    finally:
        session.close()


def test_export_gate_enforcement(db_session):
    ds = db_session.query(Dataset).first()
    report = create_initial_report(db_session, ds.id)

    # 1. Export in DRAFT must fail
    with pytest.raises(HTTPException) as exc:
        export_approved_report(db_session, report.id)
    assert exc.value.status_code == 400
    assert "DRAFT" in exc.value.detail

    # 2. Submit for review
    v1 = submit_report_for_review(db_session, report.id)

    # Export while SUBMITTED must fail
    with pytest.raises(HTTPException) as exc:
        export_approved_report(db_session, report.id)
    assert exc.value.status_code == 400
    assert "awaiting review" in exc.value.detail

    # 3. Reject report
    reject_req = ReviewDecisionRequest(
        version_id=v1.id,
        decision="reject",
        comment="Evidence is incomplete, please revise."
    )
    v1_rejected = process_review_decision(db_session, report.id, reject_req, reviewer_id="chief-reviewer")
    assert v1_rejected.status == "REJECTED"

    # Export on REJECTED must fail
    with pytest.raises(HTTPException) as exc:
        export_approved_report(db_session, report.id)
    assert exc.value.status_code == 400
    assert "rejected" in exc.value.detail

    # 4. Analyst edits rejected report -> creates version 2
    edit_req = DraftReportEditRequest(title="Revised Report with Extra Evidence")
    v2 = edit_draft_report(db_session, report.id, edit_req)
    assert v2.version_number == 2
    assert v2.status == "DRAFT"

    # Submit version 2
    v2_submitted = submit_report_for_review(db_session, report.id)
    assert v2_submitted.status == "SUBMITTED"

    # 5. Reviewer approves version 2
    approve_req = ReviewDecisionRequest(
        version_id=v2_submitted.id,
        decision="approve",
        comment="Approved: All evidence verified and remedies prioritized."
    )
    v2_approved = process_review_decision(db_session, report.id, approve_req, reviewer_id="chief-reviewer")
    assert v2_approved.status == "APPROVED"

    # 6. Export approved version 2 -> MUST SUCCEED
    exported_data = export_approved_report(db_session, report.id)
    assert exported_data["export_status"] == "exported"
    assert exported_data["version_number"] == 2
    assert exported_data["content_hash"] == v2_approved.content_hash
    assert len(exported_data["review_decisions"]) == 1
    assert exported_data["review_decisions"][0]["decision"] == "approve"

