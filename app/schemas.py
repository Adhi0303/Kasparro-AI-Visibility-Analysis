from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
import os
from pathlib import Path


# --- Ingestion Schemas ---

class DatasetImportRequest(BaseModel):
    dataset_name: str = Field(default="kasparro-historical-snapshot", min_length=1, max_length=100)
    source_directory: str = Field(default="data", min_length=1, max_length=300)

    @field_validator("source_directory")
    @classmethod
    def validate_directory_path(cls, v: str) -> str:
        from app.config import get_settings

        # Keep request-shape checks here. Filesystem authorization is enforced
        # by validate_safe_source_directory in the ingestion service, where
        # configured roots and symlink targets can be checked consistently.
        if not v or not v.strip() or "\x00" in v:
            raise ValueError("source_directory must be a non-empty valid relative path")
        raw_parts = v.replace("\\", "/").split("/")
        if ".." in raw_parts:
            raise ValueError("Path traversal segments ('..') are not permitted in source_directory")
        if os.path.isabs(v):
            raise ValueError("Absolute paths are not permitted for source_directory")

        cwd = Path.cwd().resolve()
        allowed_raw = os.getenv("ALLOWED_IMPORT_DIRS") or get_settings().ALLOWED_IMPORT_DIRS
        allowed_dirs = [
            (cwd / entry.strip()).resolve()
            for entry in allowed_raw.split(",")
            if entry.strip()
        ]
        resolved = (cwd / v).resolve()
        if not any(resolved.is_relative_to(root) for root in allowed_dirs):
            raise ValueError("source_directory must resolve inside an authorized import directory")
        return v


class InvalidRecordInfo(BaseModel):
    file: str
    line_number: int
    record_id: Optional[str] = None
    reason: str


class DatasetImportResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    imported_prompts: int
    imported_responses: int
    imported_citations: int
    invalid_records: List[InvalidRecordInfo] = []
    validation_status: str


# --- Analysis Schemas ---

class AnalysisRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1)
    execution_mode: Literal["replay", "real_model"] = Field(default="replay")
    classifier_version: Literal["v1", "v2"] = Field(default="v1")
    scoring_version: Literal["v1", "v2"] = Field(default="v1")


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    dataset_id: str
    status: str
    execution_mode: str
    classifier_version: str
    scoring_version: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_eligible: int = 0
    total_successful: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    mean_score: Optional[float] = None
    engine_aggregates: Dict[str, Any] = {}
    category_aggregates: Dict[str, Any] = {}


# --- Report Schemas ---

class DiagnosticItem(BaseModel):
    title: str
    observed_pattern: str
    comparison: Optional[str] = None
    evidence: List[Dict[str, Any]]  # response_id, engine, prompt, excerpt
    possible_explanation: str
    validation_needed: str
    confidence_and_limitations: str


class RemedyItem(BaseModel):
    title: str
    problem: str
    supporting_evidence: List[str]  # response_ids
    action: str
    expected_benefit: str
    effort: str
    uncertainty: str
    validation: str


class DraftReportEditRequest(BaseModel):
    title: Optional[str] = None
    diagnostics: Optional[List[DiagnosticItem]] = None
    remedies: Optional[List[RemedyItem]] = None


class ReviewDecisionRequest(BaseModel):
    version_id: str
    decision: str = Field(..., pattern="^(approve|reject)$")
    comment: str


class ReportVersionResponse(BaseModel):
    report_id: str
    version_id: str
    version_number: int
    status: str
    content_hash: str
    created_by: str
    created_at: datetime
    submitted_at: Optional[datetime] = None
    content: Dict[str, Any]
    review_decisions: List[Dict[str, Any]] = []

