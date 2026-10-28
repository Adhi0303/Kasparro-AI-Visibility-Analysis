import re
from typing import Optional, List
from app.llm.base import LLMBase, ClassificationResult, EvidenceItem

KNOWN_COMPETITORS = [
    "profound",
    "peec ai",
    "otterly",
    "brightedge",
    "revenuezen",
    "empact partners",
    "empact",
    "kaspr",
    "gaspar ai",
    "first page sage",
]

RECOMMENDATION_KEYWORDS = [
    r"\brecommend(s|ed|ing)?\b",
    r"\btop\s+(choice|pick|option|tool|agency)\b",
    r"\bsuitable\s+option\b",
    r"\bworth\s+considering\b",
    r"\bcan\s+help\b",
    r"\bstrong\s+contender\b",
    r"\bgood\s+choice\b",
]

NEGATIVE_KEYWORDS = [
    r"\bnot\s+(a\s+)?widely\s+recognized\b",
    r"\bcautio(us|n)\b",
    r"\bscam(adviser)?\b",
    r"\blacks?\s+(independent\s+)?evidence\b",
    r"\blacks?\s+(verifiable\s+)?case\s+studies\b",
    r"\bunproven\b",
    r"\bnot\s+recommend\b",
    r"\bwarning\b",
    r"\bunreliable\b",
    r"\bno\s+independent\s+(data|reviews|validation)\b",
    r"\bwould\s+not\s+expect\b",
]


class ReplayClassifier(LLMBase):
    def __init__(self, classifier_version: str = "v1"):
        self.classifier_version = classifier_version

    def classify(
        self,
        response_id: str,
        engine: str,
        answer_text: str,
        failure_scenario: Optional[str] = None
    ) -> ClassificationResult:
        # Handle simulated failure scenarios
        if failure_scenario == "permanent_timeout":
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="failed",
                failure_reason="Model provider timeout: retry bound reached",
                execution_mode="replay",
                classifier_version=self.classifier_version,
            )
        elif failure_scenario == "malformed":
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="failed",
                failure_reason="Malformed model response: schema validation failed",
                execution_mode="replay",
                classifier_version=self.classifier_version,
            )
        elif failure_scenario == "empty":
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="failed",
                failure_reason="Empty response payload returned by provider",
                execution_mode="replay",
                classifier_version=self.classifier_version,
            )

        if not answer_text or not answer_text.strip():
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="skipped",
                failure_reason="Answer text is empty",
                execution_mode="replay",
                classifier_version=self.classifier_version,
            )

        text_lower = answer_text.lower()
        has_mention = "kasparro" in text_lower

        if not has_mention:
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="success",
                kasparro_absent=True,
                kasparro_mentioned=False,
                kasparro_recommended=False,
                kasparro_negative=False,
                competitors=self._find_competitors(text_lower),
                recommendation_position=None,
                evidence=[],
                confidence=1.0,
                execution_mode="replay",
                classifier_version=self.classifier_version,
            )

        # Kasparro is mentioned: extract verbatim sentence excerpts as evidence
        evidence_items = self._extract_evidence(answer_text)

        # Check negative characterization
        is_negative = False
        for pat in NEGATIVE_KEYWORDS:
            if re.search(pat, text_lower):
                is_negative = True
                break

        # Check recommendation
        is_recommended = False
        for pat in RECOMMENDATION_KEYWORDS:
            # Check if recommendation keyword co-occurs near kasparro or general recommendation
            if re.search(pat, text_lower) and not is_negative:
                is_recommended = True
                break

        # Determine recommendation position if present in ordered lists
        position = self._extract_position(answer_text)

        # Find competitor mentions
        competitors = self._find_competitors(text_lower)

        return ClassificationResult(
            response_id=response_id,
            engine=engine,
            status="success",
            kasparro_absent=False,
            kasparro_mentioned=True,
            kasparro_recommended=is_recommended,
            kasparro_negative=is_negative,
            competitors=competitors,
            recommendation_position=position,
            evidence=evidence_items,
            confidence=0.95,
            execution_mode="replay",
            classifier_version=self.classifier_version,
        )

    def _extract_evidence(self, text: str) -> List[EvidenceItem]:
        evidence = []
        # Split text into paragraphs or sentences
        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        for s in sentences:
            s_clean = s.strip()
            if "kasparro" in s_clean.lower() and len(s_clean) > 10:
                # Truncate cleanly if too long, keeping verbatim substring
                sub = s_clean[:250].strip()
                # Verify exact verbatim match in source text
                if sub in text:
                    evidence.append(EvidenceItem(excerpt=sub, location="answer_text"))
                if len(evidence) >= 3:
                    break
        return evidence

    def _extract_position(self, text: str) -> Optional[int]:
        lines = text.split("\n")
        for line in lines:
            m = re.match(r"^\s*(\d+)[\.\)]\s+.*kasparro", line, re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
        return None

    def _find_competitors(self, text_lower: str) -> List[str]:
        found = []
        for comp in KNOWN_COMPETITORS:
            if comp in text_lower and comp not in found:
                found.append(comp)
        return found

