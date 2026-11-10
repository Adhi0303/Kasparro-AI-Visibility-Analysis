from contextlib import asynccontextmanager
from email.parser import BytesParser
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import (
    AuthenticatedActor,
    require_analyst_actor,
    require_authenticated_actor,
    require_reviewer_actor,
)
from app.classification import execute_analysis, get_analysis_status
from app.config import get_settings
from app.database import get_db, init_db
from app.export import export_approved_report
from app.ingestion import (
    ImportLimitError,
    PathSecurityError,
    import_dataset,
)
from app.models import AnalysisRun, Dataset, Report, ReportVersion
from app.reports import create_initial_report, edit_draft_report, submit_report_for_review
from app.review import process_review_decision
from app.schemas import (
    AnalysisRequest,
    AnalysisStatusResponse,
    DatasetImportRequest,
    DatasetImportResponse,
    DraftReportEditRequest,
    ReviewDecisionRequest,
)

ALLOWED_UPLOAD_EXTENSIONS = {".jsonl"}
ALLOWED_UPLOAD_MIME_TYPES = {
    "",
    "application/json",
    "application/jsonl",
    "application/x-ndjson",
    "application/ndjson",
    "text/plain",
    "application/octet-stream",
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Kasparro AI Visibility Analysis & Human Review Service",
    version="1.0.0",
    description="Backend service for analyzing brand visibility across AI engines with evidence tracking and approval gates.",
    lifespan=lifespan,
)


@app.middleware("http")
async def enforce_request_size_limit(request: Request, call_next):
    """Enforce the request limit from streamed bytes, even when Content-Length is absent or false."""
    settings = get_settings()
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            length_val = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid Content-Length header"},
            )
        if length_val < 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid Content-Length header"},
            )

    body_chunks = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > settings.MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={"detail": "Request payload exceeds maximum allowed size"},
            )
        body_chunks.append(chunk)

    body = b"".join(body_chunks)
    if content_length is not None and total_bytes != int(content_length):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Request body length does not match Content-Length"},
        )

    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    bounded_request = Request(request.scope, receive=receive)
    return await call_next(bounded_request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def _get_allowed_import_roots() -> List[Path]:
    settings = get_settings()
    raw = os.getenv("ALLOWED_IMPORT_DIRS") or settings.ALLOWED_IMPORT_DIRS
    cwd = Path.cwd().resolve()
    return [(cwd / entry.strip()).resolve() for entry in raw.split(",") if entry.strip()]


def _ensure_dataset_access(dataset: Optional[Dataset], actor: AuthenticatedActor) -> Dataset:
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if actor.role == "admin":
        return dataset
    if actor.role == "analyst" and dataset.owner_id == actor.user_id:
        return dataset
    raise HTTPException(status_code=403, detail="Access forbidden: You do not own this dataset")


def _ensure_analysis_access(analysis: Optional[AnalysisRun], actor: AuthenticatedActor) -> AnalysisRun:
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if actor.role in ("admin", "reviewer"):
        return analysis
    if analysis.created_by == actor.user_id:
        return analysis
    raise HTTPException(status_code=403, detail="Access forbidden: You do not own this analysis")


def _ensure_report_access(
    report: Optional[Report],
    actor: AuthenticatedActor,
    allow_reviewer: bool = True,
) -> Report:
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if actor.role == "admin":
        return report
    if allow_reviewer and actor.role == "reviewer":
        return report
    if actor.role == "analyst" and report.owner_id == actor.user_id:
        return report
    raise HTTPException(status_code=403, detail="Access forbidden: You do not own this report")


def _validate_and_write_uploaded_part(
    raw_filename: Optional[str],
    mime_type: Optional[str],
    payload_bytes: bytes,
    target_path: Path,
    max_file_bytes: int,
) -> None:
    raw_name = raw_filename or ""
    if not raw_name or "\x00" in raw_name or ".." in raw_name.replace("\\", "/").split("/"):
        raise HTTPException(status_code=400, detail="Invalid uploaded filename")
    clean_name = os.path.basename(raw_name.replace("\\", "/")).strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Invalid uploaded filename")

    suffix = Path(clean_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS or len(Path(clean_name).suffixes) > 1:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file extension: only .jsonl files are allowed",
        )

    mime = (mime_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_UPLOAD_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file MIME type for JSONL upload",
        )

    if len(payload_bytes) > max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Uploaded file exceeds maximum permitted size",
        )

    if b"\x00" in payload_bytes:
        raise HTTPException(
            status_code=400,
            detail="Invalid binary content detected in uploaded file",
        )

    try:
        decoded = payload_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded file must be valid UTF-8 text")

    target_path.write_text(decoded, encoding="utf-8")


async def _parse_multipart_upload(
    request: Request,
    max_body_bytes: int,
) -> Tuple[Dict[str, str], Dict[str, Tuple[Optional[str], Optional[str], bytes]]]:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data") or "boundary=" not in content_type.lower():
        raise HTTPException(status_code=400, detail="Content-Type must be multipart/form-data with boundary")

    chunks: List[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_body_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Request payload exceeds maximum allowed size",
            )
        chunks.append(chunk)

    raw_body = b"".join(chunks)
    header_prefix = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("latin-1")
    message = BytesParser().parsebytes(header_prefix + raw_body)
    if not message.is_multipart():
        raise HTTPException(status_code=400, detail="Malformed multipart upload payload")

    fields: Dict[str, str] = {}
    files: Dict[str, Tuple[Optional[str], Optional[str], bytes]] = {}
    for part in message.get_payload():
        field_name = part.get_param("name", header="content-disposition")
        if not isinstance(field_name, str) or not field_name:
            continue
        filename = part.get_filename()
        raw_payload = part.get_payload(decode=True) or b""
        if filename is not None:
            if field_name in files or field_name in fields:
                raise HTTPException(status_code=400, detail="Duplicate multipart field is not allowed")
            files[field_name] = (filename, part.get_content_type(), raw_payload)
        else:
            if field_name in fields or field_name in files:
                raise HTTPException(status_code=400, detail="Duplicate multipart field is not allowed")
            try:
                fields[field_name] = raw_payload.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="Multipart form fields must be valid UTF-8")
    return fields, files


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/datasets", response_model=DatasetImportResponse, tags=["Datasets"])
def import_dataset_endpoint(
    req: DatasetImportRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_analyst_actor),
):
    settings = get_settings()
    try:
        return import_dataset(
            db,
            req.dataset_name,
            req.source_directory,
            owner_id=actor.user_id,
            allowed_roots=_get_allowed_import_roots(),
            max_file_bytes=settings.MAX_IMPORT_FILE_BYTES,
            max_records_per_file=settings.MAX_IMPORT_RECORDS_PER_FILE,
        )
    except PathSecurityError:
        raise HTTPException(status_code=400, detail="Invalid or unauthorized dataset directory")
    except ImportLimitError:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Dataset import exceeds resource limits")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset source directory not found")
    except Exception:
        raise HTTPException(status_code=500, detail="Dataset import failed")


@app.post("/datasets/upload", response_model=DatasetImportResponse, tags=["Datasets"])
async def upload_dataset_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_analyst_actor),
):
    settings = get_settings()
    try:
        fields, files = await _parse_multipart_upload(request, settings.MAX_REQUEST_BODY_BYTES)
        dataset_name = (fields.get("dataset_name") or "").strip()
        if not dataset_name or len(dataset_name) > 100:
            raise HTTPException(status_code=400, detail="dataset_name must be between 1 and 100 characters")
        if "responses_file" not in files:
            raise HTTPException(status_code=400, detail="responses_file is required")

        allowed_upload_fields = {"prompts_file", "responses_file", "citations_file"}
        unexpected_fields = set(files.keys()) - allowed_upload_fields
        if unexpected_fields:
            raise HTTPException(status_code=400, detail="Unexpected uploaded file field")

        field_to_canonical = {
            "prompts_file": "prompts.jsonl",
            "responses_file": "responses.jsonl",
            "citations_file": "citations.jsonl",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for field_key, canonical_name in field_to_canonical.items():
                if field_key in files:
                    raw_name, mime_type, raw_bytes = files[field_key]
                    _validate_and_write_uploaded_part(
                        raw_filename=raw_name,
                        mime_type=mime_type,
                        payload_bytes=raw_bytes,
                        target_path=tmp_path / canonical_name,
                        max_file_bytes=settings.MAX_IMPORT_FILE_BYTES,
                    )

            return import_dataset(
                db,
                dataset_name=dataset_name,
                source_directory=tmpdir,
                owner_id=actor.user_id,
                max_file_bytes=settings.MAX_IMPORT_FILE_BYTES,
                max_records_per_file=settings.MAX_IMPORT_RECORDS_PER_FILE,
            )
    except HTTPException:
        raise
    except ImportLimitError:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Uploaded dataset exceeds resource limits")
    except Exception:
        raise HTTPException(status_code=500, detail="Dataset upload failed")


@app.get("/datasets", tags=["Datasets"])
def list_datasets_endpoint(
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_authenticated_actor),
) -> List[Dict[str, Any]]:
    query = db.query(Dataset)
    if actor.role == "analyst":
        query = query.filter(Dataset.owner_id == actor.user_id)
    elif actor.role != "admin":
        raise HTTPException(status_code=403, detail="Access forbidden: Requires analyst or admin privileges")
    return [
        {
            "dataset_id": d.id,
            "dataset_name": d.name,
            "owner_id": d.owner_id,
            "validation_status": d.validation_status,
            "created_at": d.created_at.isoformat(),
        }
        for d in query.order_by(Dataset.created_at.desc()).all()
    ]


@app.get("/datasets/{id}", tags=["Datasets"])
def get_dataset_endpoint(
    id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_authenticated_actor),
) -> Dict[str, Any]:
    ds = _ensure_dataset_access(db.query(Dataset).filter(Dataset.id == id).first(), actor)
    return {
        "dataset_id": ds.id,
        "dataset_name": ds.name,
        "owner_id": ds.owner_id,
        "source_hash": ds.source_hash,
        "validation_status": ds.validation_status,
        "created_at": ds.created_at.isoformat(),
    }


@app.delete("/datasets/{id}", tags=["Datasets"])
def delete_dataset_endpoint(
    id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_authenticated_actor),
) -> Dict[str, str]:
    ds = _ensure_dataset_access(db.query(Dataset).filter(Dataset.id == id).first(), actor)
    try:
        db.delete(ds)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete dataset")
    return {"status": "deleted", "dataset_id": id}


@app.post("/analyses", tags=["Analysis"])
def start_analysis_endpoint(
    req: AnalysisRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_analyst_actor),
) -> Dict[str, str]:
    dataset = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
    _ensure_dataset_access(dataset, actor)

    try:
        analysis = execute_analysis(
            db,
            dataset_id=req.dataset_id,
            execution_mode=req.execution_mode,
            classifier_version=req.classifier_version,
            scoring_version=req.scoring_version,
            created_by=actor.user_id,
        )
        return {"analysis_id": analysis.id, "status": analysis.status}
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Analysis exceeded configured timeout")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid analysis configuration")
    except Exception:
        raise HTTPException(status_code=500, detail="Analysis execution failed")


@app.get("/analyses/{id}", response_model=AnalysisStatusResponse, tags=["Analysis"])
def get_analysis_endpoint(
    id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_authenticated_actor),
):
    if actor.role not in ("analyst", "reviewer", "admin"):
        raise HTTPException(status_code=403, detail="Access forbidden")
    analysis = db.query(AnalysisRun).filter(AnalysisRun.id == id).first()
    _ensure_analysis_access(analysis, actor)
    return get_analysis_status(db, id)


@app.post("/reports", tags=["Reports"])
def create_report_endpoint(
    dataset_id: str = Query(...),
    analysis_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_analyst_actor),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    _ensure_dataset_access(dataset, actor)

    if analysis_id is not None:
        analysis = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_id).first()
        _ensure_analysis_access(analysis, actor)
        if analysis.dataset_id != dataset_id:
            raise HTTPException(status_code=400, detail="Analysis does not belong to specified dataset")

    report = create_initial_report(db, dataset_id, analysis_id, owner_id=actor.user_id)
    return {"report_id": report.id, "current_draft_version_id": report.current_draft_version_id}


@app.get("/reports/{id}", tags=["Reports"])
def get_report_endpoint(
    id: str,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_authenticated_actor),
) -> Dict[str, Any]:
    report = _ensure_report_access(
        db.query(Report).filter(Report.id == id).first(),
        actor,
        allow_reviewer=True,
    )
    latest_version = (
        db.query(ReportVersion)
        .filter(ReportVersion.report_id == report.id)
        .order_by(ReportVersion.version_number.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=404, detail="No report versions found")
    return {
        "report_id": report.id,
        "dataset_id": report.dataset_id,
        "owner_id": report.owner_id,
        "version_id": latest_version.id,
        "version_number": latest_version.version_number,
        "status": latest_version.status,
        "content_hash": latest_version.content_hash,
        "content": json.loads(latest_version.content_json),
    }


@app.patch("/reports/{id}", tags=["Reports"])
def edit_report_draft_endpoint(
    id: str,
    req: DraftReportEditRequest,
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_analyst_actor),
):
    report = db.query(Report).filter(Report.id == id).first()
    _ensure_report_access(report, actor, allow_reviewer=False)

    version = edit_draft_report(db, id, req, editor_role=actor.user_id)
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
    actor: AuthenticatedActor = Depends(require_analyst_actor),
):
    report = db.query(Report).filter(Report.id == id).first()
    _ensure_report_access(report, actor, allow_reviewer=False)

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
    actor: AuthenticatedActor = Depends(require_reviewer_actor),
):
    report = db.query(Report).filter(Report.id == id).first()
    if report and report.owner_id == actor.user_id:
        raise HTTPException(status_code=403, detail="Access forbidden: Self-review is not permitted")

    version = process_review_decision(db, id, req, reviewer_id=actor.user_id)
    return {
        "report_id": id,
        "version_id": version.id,
        "version_number": version.version_number,
        "status": version.status,
    }


@app.get("/reports/{id}/export", tags=["Export"])
def export_report_endpoint(
    id: str,
    format: Literal["json", "markdown", "html"] = Query(default="json"),
    db: Session = Depends(get_db),
    actor: AuthenticatedActor = Depends(require_authenticated_actor),
):
    if actor.role not in ("analyst", "reviewer", "admin"):
        raise HTTPException(status_code=403, detail="Access forbidden")
    report = db.query(Report).filter(Report.id == id).first()
    _ensure_report_access(report, actor, allow_reviewer=True)
    return export_approved_report(db, id, output_format=format)
