from app.llm.base import LLMBase, ClassificationResult, EvidenceItem
from app.llm.replay import ReplayClassifier
from app.llm.provider import ProviderClassifier
from app.config import Settings


def get_classifier(settings: Settings, execution_mode: str = "replay", classifier_version: str = "v1") -> LLMBase:
    if execution_mode == "real_model":
        return ProviderClassifier(settings, classifier_version=classifier_version)
    return ReplayClassifier(classifier_version=classifier_version)


__all__ = ["LLMBase", "ClassificationResult", "EvidenceItem", "ReplayClassifier", "ProviderClassifier", "get_classifier"]

