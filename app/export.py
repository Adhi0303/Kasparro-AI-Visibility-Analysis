import json
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import Report, ReportVersion, ReviewDecision


def export_approved_report(db: Session, report_id: str) -> Dict[str, Any]:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    latest_version = (
        db.query(ReportVersion)
        .filter(ReportVersion.report_id == report_id)
        .order_by(ReportVersion.version_number.desc())
        .first()
    )

    if not latest_version:
        raise HTTPException(status_code=404, detail="No report versions found")

    # Gate checks
    if latest_version.status == "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export rejected: Report is in DRAFT state. Must be submitted and approved by reviewer."
        )

    if latest_version.status == "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export rejected: Report version is awaiting review. Approval is required before export."
        )

    if latest_version.status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export rejected: Report version was rejected by reviewer."
        )

    if latest_version.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export rejected: Invalid version status '{latest_version.status}'."
        )

    # Fetch review decision
    decisions = (
        db.query(ReviewDecision)
        .filter(ReviewDecision.report_version_id == latest_version.id)
        .all()
    )

    decisions_list = [
        {
            "reviewer_id": d.reviewer_id,
            "decision": d.decision,
            "comment": d.comment,
            "created_at": d.created_at.isoformat()
        }
        for d in decisions
    ]

    return {
        "export_status": "exported",
        "exported_at": datetime.utcnow().isoformat(),
        "report_id": report.id,
        "version_id": latest_version.id,
        "version_number": latest_version.version_number,
        "content_hash": latest_version.content_hash,
        "content": json.loads(latest_version.content_json),
        "review_decisions": decisions_list,
    }

