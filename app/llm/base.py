from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    excerpt: str
    location: str = "answer_text"
    citation_id: Optional[str] = None


class ClassificationResult(BaseModel):
    response_id: str
    engine: Optional[str] = None
    status: str = Field(default="success")  # success, failed, skipped
    kasparro_absent: bool = False
    kasparro_mentioned: bool = False
    kasparro_recommended: bool = False
    kasparro_negative: bool = False
    competitors: List[str] = Field(default_factory=list)
    recommendation_position: Optional[int] = None
    citation_ids: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    confidence: Optional[float] = None
    failure_reason: Optional[str] = None
    execution_mode: str = "replay"
    classifier_version: str = "v1"


class LLMBase(ABC):
    @abstractmethod
    def classify(self, response_id: str, engine: str, answer_text: str, failure_scenario: Optional[str] = None) -> ClassificationResult:
        """Classify a single response."""
        pass

