import json
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.evidence import (
    render_report_html,
    render_report_markdown,
    validate_report_evidence,
)
from app.models import Report, ReportVersion, Response as DBResponse, ReviewDecision


def _build_source_lookup(db: Session, dataset_id: str) -> Dict[str, Dict[str, str]]:
    responses = db.query(DBResponse).filter(DBResponse.dataset_id == dataset_id).all()
    lookup: Dict[str, Dict[str, str]] = {}
    for resp in responses:
        try:
            payload = json.loads(resp.raw_payload)
        except Exception:
            payload = {}
        lookup[resp.source_response_id] = {"answer_text": payload.get("answer_text", "")}
    return lookup


def export_approved_report(
    db: Session,
    report_id: str,
    output_format: str = "json",
) -> Dict[str, Any]:
    if output_format not in ("json", "markdown", "html"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format '{output_format}'. Expected 'json', 'markdown', or 'html'.",
        )

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
            detail="Export rejected: Report is in DRAFT state. Must be submitted and approved by reviewer.",
        )

    if latest_version.status == "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export rejected: Report version is awaiting review. Approval is required before export.",
        )

    if latest_version.status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export rejected: Report version was rejected by reviewer.",
        )

    if latest_version.status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export rejected: Invalid version status '{latest_version.status}'.",
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
            "created_at": d.created_at.isoformat(),
        }
        for d in decisions
    ]

    content = json.loads(latest_version.content_json)
    source_lookup = _build_source_lookup(db, report.dataset_id)
    validated_diagnostics, audit_summary = validate_report_evidence(
        content.get("diagnostics", []),
        source_lookup,
    )
    content["diagnostics"] = validated_diagnostics
    content["evidence_validation"] = audit_summary

    result: Dict[str, Any] = {
        "export_status": "exported",
        "exported_at": datetime.utcnow().isoformat(),
        "report_id": report.id,
        "version_id": latest_version.id,
        "version_number": latest_version.version_number,
        "content_hash": latest_version.content_hash,
        "content": content,
        "review_decisions": decisions_list,
    }
    if output_format == "markdown":
        result["format"] = "markdown"
        result["rendered"] = render_report_markdown(content, source_lookup=source_lookup)
    elif output_format == "html":
        result["format"] = "html"
        result["rendered"] = render_report_html(content, source_lookup=source_lookup)
    return result
