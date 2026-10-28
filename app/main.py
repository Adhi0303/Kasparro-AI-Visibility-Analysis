from fastapi import FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.database import get_db, init_db
from app.auth import require_analyst, require_reviewer, require_analyst_or_reviewer
from app.schemas import (
    DatasetImportRequest,
    DatasetImportResponse,
    AnalysisRequest,
    AnalysisStatusResponse,
    DraftReportEditRequest,
    ReviewDecisionRequest,
)
from app.ingestion import import_dataset
from app.classification import execute_analysis, get_analysis_status
from app.reports import create_initial_report, edit_draft_report, submit_report_for_review
from app.review import process_review_decision
from app.export import export_approved_report

app = FastAPI(
    title="Kasparro AI Visibility Analysis & Human Review Service",
    version="1.0.0",
    description="Backend service for analyzing brand visibility across AI engines with evidence tracking and approval gates."
)


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/datasets", response_model=DatasetImportResponse, tags=["Datasets"])
def import_dataset_endpoint(
    req: DatasetImportRequest,
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst),
):
    try:
        return import_dataset(db, req.dataset_name, req.source_directory)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")


@app.post("/analyses", tags=["Analysis"])
def start_analysis_endpoint(
    req: AnalysisRequest,
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst),
) -> Dict[str, str]:
    analysis = execute_analysis(
        db,
        dataset_id=req.dataset_id,
        execution_mode=req.execution_mode,
        classifier_version=req.classifier_version,
        scoring_version=req.scoring_version,
    )
    return {"analysis_id": analysis.id, "status": analysis.status}


@app.get("/analyses/{id}", response_model=AnalysisStatusResponse, tags=["Analysis"])
def get_analysis_endpoint(
    id: str,
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst),
):
    try:
        return get_analysis_status(db, id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/reports", tags=["Reports"])
def create_report_endpoint(
    dataset_id: str = Query(...),
    analysis_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst),
):
    report = create_initial_report(db, dataset_id, analysis_id)
    return {"report_id": report.id, "current_draft_version_id": report.current_draft_version_id}


@app.patch("/reports/{id}", tags=["Reports"])
def edit_report_draft_endpoint(
    id: str,
    req: DraftReportEditRequest,
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst),
):
    version = edit_draft_report(db, id, req, editor_role=role)
    return {
        "report_id": id,
        "version_id": version.id,
        "version_number": version.version_number,
        "status": version.status,
        "content_hash": version.content_hash,
    }


@app.post("/reports/{id}/submit", tags=["Reports"])
def submit_report_endpoint(
    id: str,
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst),
):
    version = submit_report_for_review(db, id)
    return {
        "report_id": id,
        "version_id": version.id,
        "version_number": version.version_number,
        "status": version.status,
        "submitted_at": version.submitted_at.isoformat() if version.submitted_at else None,
    }


@app.post("/reports/{id}/decision", tags=["Review"])
def review_decision_endpoint(
    id: str,
    req: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    role: str = Depends(require_reviewer),
):
    version = process_review_decision(db, id, req, reviewer_id=role)
    return {
        "report_id": id,
        "version_id": version.id,
        "version_number": version.version_number,
        "status": version.status,
    }


@app.get("/reports/{id}/export", tags=["Export"])
def export_report_endpoint(
    id: str,
    db: Session = Depends(get_db),
    role: str = Depends(require_analyst_or_reviewer),
):
    return export_approved_report(db, id)

