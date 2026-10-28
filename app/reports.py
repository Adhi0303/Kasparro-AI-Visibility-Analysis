import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import Report, ReportVersion, Dataset, AnalysisRun
from app.diagnostics import get_default_diagnostics
from app.remedies import get_default_remedies
from app.schemas import DraftReportEditRequest, ReportVersionResponse


def compute_content_hash(content: Dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_initial_report(db: Session, dataset_id: str, analysis_id: Optional[str] = None) -> Report:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    report = Report(dataset_id=dataset_id)
    db.add(report)
    db.flush()

    # Load analysis results if available
    analysis_data = {}
    if analysis_id:
        analysis = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_id).first()
        if analysis and analysis.configuration_json:
            analysis_data = json.loads(analysis.configuration_json)

    initial_content = {
        "title": "Kasparro AI Visibility Analysis Snapshot",
        "dataset_name": dataset.name,
        "source_hash": dataset.source_hash,
        "analysis_summary": analysis_data,
        "diagnostics": get_default_diagnostics(),
        "remedies": get_default_remedies(),
    }

    content_hash = compute_content_hash(initial_content)

    version = ReportVersion(
        report_id=report.id,
        version_number=1,
        status="DRAFT",
        content_json=json.dumps(initial_content),
        content_hash=content_hash,
        created_by="analyst",
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.flush()

    report.current_draft_version_id = version.id
    db.commit()
    return report


def edit_draft_report(
    db: Session,
    report_id: str,
    edit_req: DraftReportEditRequest,
    editor_role: str = "analyst"
) -> ReportVersion:
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
        raise HTTPException(status_code=404, detail="No versions exist for report")

    content = json.loads(latest_version.content_json)

    # If the latest version is already SUBMITTED or APPROVED or REJECTED,
    # editing must create a NEW draft version, leaving historical version immutable!
    if latest_version.status in ("SUBMITTED", "APPROVED", "REJECTED"):
        new_version_number = latest_version.version_number + 1

        if edit_req.title is not None:
            content["title"] = edit_req.title
        if edit_req.diagnostics is not None:
            content["diagnostics"] = [d.model_dump() for d in edit_req.diagnostics]
        if edit_req.remedies is not None:
            content["remedies"] = [r.model_dump() for r in edit_req.remedies]

        new_hash = compute_content_hash(content)

        new_draft = ReportVersion(
            report_id=report.id,
            version_number=new_version_number,
            status="DRAFT",
            content_json=json.dumps(content),
            content_hash=new_hash,
            created_by=editor_role,
            created_at=datetime.utcnow(),
        )
        db.add(new_draft)
        db.flush()
        report.current_draft_version_id = new_draft.id
        db.commit()
        return new_draft
    else:
        # Currently in DRAFT: update in place
        if edit_req.title is not None:
            content["title"] = edit_req.title
        if edit_req.diagnostics is not None:
            content["diagnostics"] = [d.model_dump() for d in edit_req.diagnostics]
        if edit_req.remedies is not None:
            content["remedies"] = [r.model_dump() for r in edit_req.remedies]

        latest_version.content_json = json.dumps(content)
        latest_version.content_hash = compute_content_hash(content)
        db.commit()
        return latest_version


def submit_report_for_review(db: Session, report_id: str) -> ReportVersion:
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
        raise HTTPException(status_code=404, detail="No versions found to submit")

    if latest_version.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit version with status '{latest_version.status}'. Must be in DRAFT."
        )

    latest_version.status = "SUBMITTED"
    latest_version.submitted_at = datetime.utcnow()
    db.commit()
    return latest_version

