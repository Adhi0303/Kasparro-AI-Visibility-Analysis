import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import Dataset, Report, ReportVersion
from app.reports import create_initial_report, edit_draft_report, submit_report_for_review
from app.schemas import DraftReportEditRequest


@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    try:
        # Create dummy dataset
        ds = Dataset(name="test-ds", source_hash="dummy-hash", validation_status="valid")
        session.add(ds)
        session.commit()
        yield session
    finally:
        session.close()


def test_report_lifecycle_and_immutability(db_session):
    ds = db_session.query(Dataset).first()

    # 1. Create initial report
    report = create_initial_report(db_session, ds.id)
    assert report.id is not None
    v1 = db_session.query(ReportVersion).filter(ReportVersion.report_id == report.id).first()
    assert v1.version_number == 1
    assert v1.status == "DRAFT"

    # 2. Edit draft in place
    edit_req = DraftReportEditRequest(title="Updated Title v1")
    v1_updated = edit_draft_report(db_session, report.id, edit_req)
    assert v1_updated.version_number == 1
    assert v1_updated.status == "DRAFT"

    # 3. Submit report
    submitted_v1 = submit_report_for_review(db_session, report.id)
    assert submitted_v1.status == "SUBMITTED"
    assert submitted_v1.submitted_at is not None

    # Cannot submit again when not DRAFT
    with pytest.raises(HTTPException) as exc:
        submit_report_for_review(db_session, report.id)
    assert exc.value.status_code == 400

    # 4. Edit after submission: MUST create a NEW draft (version 2)
    edit_req_2 = DraftReportEditRequest(title="New Draft Title v2")
    v2_draft = edit_draft_report(db_session, report.id, edit_req_2)
    assert v2_draft.version_number == 2
    assert v2_draft.status == "DRAFT"

    # Check v1 remains frozen as SUBMITTED
    v1_check = db_session.query(ReportVersion).filter(ReportVersion.version_number == 1).first()
    assert v1_check.status == "SUBMITTED"
    assert "Updated Title v1" in v1_check.content_json

