from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import ReportVersion, ReviewDecision
from app.schemas import ReviewDecisionRequest


def process_review_decision(
    db: Session,
    report_id: str,
    decision_req: ReviewDecisionRequest,
    reviewer_id: str = "reviewer"
) -> ReportVersion:
    version = db.query(ReportVersion).filter(ReportVersion.id == decision_req.version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Report version not found")

    if version.report_id != report_id:
        raise HTTPException(status_code=400, detail="Version does not belong to specified report")

    if version.status != "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review version with status '{version.status}'. Must be SUBMITTED."
        )

    decision_norm = decision_req.decision.lower()
    if decision_norm not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decision must be 'approve' or 'reject'")

    try:
        review = ReviewDecision(
            report_version_id=version.id,
            reviewer_id=reviewer_id,
            decision=decision_norm,
            comment=decision_req.comment,
            created_at=datetime.utcnow()
        )
        db.add(review)

        version.status = "APPROVED" if decision_norm == "approve" else "REJECTED"
        db.commit()
        return version
    except Exception:
        db.rollback()
        raise

