import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    owner_id = Column(String, nullable=False, default="analyst-1")
    source_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    validation_status = Column(String, nullable=False, default="valid")

    responses = relationship("Response", back_populates="dataset", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="dataset", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="dataset", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id = Column(String, primary_key=True, default=generate_uuid)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    source_response_id = Column(String, nullable=False)
    prompt_id = Column(String, nullable=False)
    engine = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=False)  # JSON text
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "source_response_id", name="uq_dataset_source_response"),
    )

    dataset = relationship("Dataset", back_populates="responses")
    results = relationship("ResponseResult", back_populates="response", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="response", cascade="all, delete-orphan")


class Citation(Base):
    __tablename__ = "citations"

    id = Column(String, primary_key=True, default=generate_uuid)
    response_id = Column(String, ForeignKey("responses.id"), nullable=False)
    source_citation_id = Column(String, nullable=False)
    prompt_id = Column(String, nullable=False)
    engine = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    citation_type = Column(String, nullable=False)
    url = Column(Text, nullable=False)
    publication_date = Column(String, nullable=True)

    response = relationship("Response", back_populates="citations")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    created_by = Column(String, nullable=False, default="analyst-1")
    execution_mode = Column(String, nullable=False, default="replay")
    classifier_version = Column(String, nullable=False, default="v1")
    scoring_version = Column(String, nullable=False, default="v1")
    status = Column(String, nullable=False, default="running")  # running, completed, failed
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    configuration_json = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="analysis_runs")
    results = relationship("ResponseResult", back_populates="analysis_run", cascade="all, delete-orphan")


class ResponseResult(Base):
    __tablename__ = "response_results"

    id = Column(String, primary_key=True, default=generate_uuid)
    analysis_id = Column(String, ForeignKey("analysis_runs.id"), nullable=False)
    response_id = Column(String, ForeignKey("responses.id"), nullable=False)
    status = Column(String, nullable=False)  # success, failed, skipped
    labels_json = Column(Text, nullable=True)
    components_json = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    evidence_json = Column(Text, nullable=True)
    failure_reason = Column(String, nullable=True)

    analysis_run = relationship("AnalysisRun", back_populates="results")
    response = relationship("Response", back_populates="results")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=generate_uuid)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    owner_id = Column(String, nullable=False, default="analyst-1")
    current_draft_version_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset = relationship("Dataset", back_populates="reports")
    versions = relationship("ReportVersion", back_populates="report", cascade="all, delete-orphan")


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    report_id = Column(String, ForeignKey("reports.id"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="DRAFT")  # DRAFT, SUBMITTED, APPROVED, REJECTED
    content_json = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False)
    created_by = Column(String, nullable=False, default="analyst")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)

    report = relationship("Report", back_populates="versions")
    decisions = relationship("ReviewDecision", back_populates="report_version", cascade="all, delete-orphan")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(String, primary_key=True, default=generate_uuid)
    report_version_id = Column(String, ForeignKey("report_versions.id"), nullable=False)
    reviewer_id = Column(String, nullable=False)
    decision = Column(String, nullable=False)  # approve, reject
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    report_version = relationship("ReportVersion", back_populates="decisions")

