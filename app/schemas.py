from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# --- Ingestion Schemas ---

class DatasetImportRequest(BaseModel):
    dataset_name: str = Field(default="kasparro-historical-snapshot")
    source_directory: str = Field(default="data")


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
    dataset_id: str
    execution_mode: str = Field(default="replay")
    classifier_version: str = Field(default="v1")
    scoring_version: str = Field(default="v1")


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

