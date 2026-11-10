import re
from typing import Optional, List, Tuple
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

PROMPT_ECHO_PREFIX_RE = re.compile(
    r"^(?:in\s+(?:response|reply)\s+to\s+)?"
    r"(?:the\s+user|you|your|this\s+(?:prompt|query|question)|the\s+(?:prompt|query|question))\b"
    r"[^.!?]*\b(?:ask(?:ed|ing)?|submit(?:ted)?|mention(?:ed)?|referenc(?:ed|ing)|inquir(?:ed|ing)|quer(?:y|ied)|search(?:ed)?|regarding|about)\b",
    re.IGNORECASE,
)

PROMPT_LABEL_PREFIX_RE = re.compile(
    r"^(?:user\s+)?(?:prompt|query|question)\s*[:\-]\s*",
    re.IGNORECASE,
)

EVALUATIVE_POST_KASPARRO_RE = re.compile(
    r"\bkasparro\b(?:\s*\([^)]*\))?\s+"
    r"(?:is|are|was|were|offers?|provides?|tracks?|helps?|competes?|lacks?|positions?|remains?|stands|serves|"
    r"delivers?|features?|supports?|can|may|should|could|will|would|seems?|appears?)\b",
    re.IGNORECASE,
)

ECHO_INDIRECT_QUESTION_RE = re.compile(
    r"\b(?:ask(?:ed|ing)?|inquir(?:ed|ing)|question(?:ed|ing)?|wonder(?:ed|ing)?)\s+(?:whether|if)\b",
    re.IGNORECASE,
)

RECOMMENDATION_NEGATION_RE = re.compile(
    r"\b(?:not|never|cannot|can't|couldn't|wouldn't|would\s+not|do\s+not|don't|hard\s+to|hesitate\s+to)\s+"
    r"(?:be\s+)?recommend(?:ed|ing|able)?\b"
    r"|\bnot\s+(?:a\s+)?(?:good\s+choice|top\s+(?:choice|pick|option|tool|agency)|strong\s+contender|suitable\s+option|viable\s+option|worth\s+(?:considering|evaluating|trying))\b",
    re.IGNORECASE,
)

KASPARRO_DIRECT_REC_RE = re.compile(
    r"\b(?:recommend(?:ed|ing|s)?|endorse|shortlist|suggest(?:s|ed|ing)?|choose|pick|go\s+with)\s+"
    r"(?:trying\s+|using\s+|evaluating\s+|testing\s+)?kasparro\b",
    re.IGNORECASE,
)

KASPARRO_PREDICATE_REC_RE = re.compile(
    r"\bkasparro\b[^.;]*\b(?:is|are|stands\s+out\s+as|serves\s+as|positions\s+itself\s+as|remains|could\s+be|may\s+be|appears\s+to\s+be)\b"
    r"[^.;]*\b(?:strong\s+(?:contender|(?:ai\s+\w+\s+)?platform|option|tool|choice)|"
    r"good\s+(?:choice|option|tool|fit)|top\s+(?:choice|pick|option|tool|agency)|"
    r"suitable\s+option|viable\s+(?:option|choice|solution|tool|provider)|"
    r"solid\s+(?:option|choice|tool|platform)|recommended(?:\s+option|\s+tool|\s+platform)?|"
    r"worth\s+(?:considering|evaluating|trying))\b"
    r"|\bkasparro\b[^.;]*\bworth\s+(?:considering|evaluating|trying)\b",
    re.IGNORECASE,
)

ANAPHOR_REC_RE = re.compile(
    r"\b(?:works?\s+well|is\s+(?:a\s+)?(?:strong\s+contender|good\s+choice|viable\s+option|worth\s+(?:considering|evaluating))|"
    r"provides?\s+much-needed\s+visibility|see\s+measurable\s+improvements)\b",
    re.IGNORECASE,
)

GENERAL_IMPROVEMENT_REC_RE = re.compile(
    r"\b(?:works?\s+well|measurable\s+improvements)\b",
    re.IGNORECASE,
)

REC_NEGATED_GUARD_RE = re.compile(
    r"\b(?:couldn't\s+find|could\s+not\s+find|would\s+not\s+expect|no\s+(?:independent\s+)?evidence)\b",
    re.IGNORECASE,
)

NEUTRAL_UNCERTAINTY_RE = re.compile(
    r"\b(?:insufficient\s+(?:public\s+)?information\s+to\s+assess|"
    r"not\s+enough\s+verified\s+information\s+to\s+judge|"
    r"couldn't\s+find\s+reliable\s+public\s+pricing|"
    r"could\s+not\s+find\s+reliable\s+public\s+pricing|"
    r"no\s+public\s+pricing\s+(?:available|listed))\b",
    re.IGNORECASE,
)

NEGATIVE_NEGATED_GUARD_RE = re.compile(
    r"\b(?:neither\s+(?:a\s+)?(?:complete\s+)?scam|not\s+a\s+scam|no\s+negative|not\s+unreliable)\b",
    re.IGNORECASE,
)

KASPARRO_NEGATIVE_PATTERNS = [
    re.compile(r"\b(?:not|never|cannot|can't|couldn't|wouldn't|would\s+not|do\s+not|don't)\s+(?:be\s+)?recommend(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:a\s+)?widely\s+recognized\b", re.IGNORECASE),
    re.compile(r"\bunreliable\b|\bunproven\b|\bquestionable\b", re.IGNORECASE),
    re.compile(r"\bscam(?:adviser)?\b|\bred\s+flags?\b", re.IGNORECASE),
    re.compile(r"\b(?:exercise|advise|urge)\s+caution\b|\breasons?\s+to\s+be\s+cautious\b", re.IGNORECASE),
    re.compile(r"\bnegative\s+reviews?\b|\bpoor\s+(?:evidence|reviews?|track\s+record|reputation)\b", re.IGNORECASE),
    re.compile(r"\blacks?\s+(?:independent\s+|verifiable\s+)?(?:case\s+studies|evidence|validation|proof|track\s+record|reviews?)\b", re.IGNORECASE),
    re.compile(r"\b(?:couldn't|could\s+not)\s+find\s+(?:independent|verifiable|third[- ]party)\s+(?:evidence|case\s+studies|data|proof)\b", re.IGNORECASE),
    re.compile(r"\bthere\s+(?:isn't|is\s+not|are\s+very\s+few)\s+(?:much\s+)?(?:independent\s+)?(?:evidence|case\s+studies|reviews?)\b", re.IGNORECASE),
    re.compile(r"\b(?:limited|no)\s+independent\s+(?:validation|evidence|case\s+studies|data|reviews?)\b", re.IGNORECASE),
    re.compile(r"\bwould\s+not\s+expect\b[^.;]*\breliably\b", re.IGNORECASE),
]

PRONOUN_REF_RE = re.compile(
    r"^(?:\*+\s*)?(?:where\s+it|it|its|they|their|this\s+(?:platform|tool|company|product|service)|the\s+(?:platform|tool|company|product|service))\b",
    re.IGNORECASE,
)

INDUSTRY_SUBJECT_RE = re.compile(
    r"\b(?:ai\s+visibility\s+(?:tracking|tools|platforms)|llms?|large\s+language\s+models?|many\s+(?:basic\s+)?(?:tools|trackers|platforms)|most\s+agencies)\b",
    re.IGNORECASE,
)


def _clean_prose_line(line: str) -> str:
    """Removes Markdown URL targets and raw URLs so slugs do not distort prose matching."""
    cleaned = re.sub(r"\[([^\]]*)\]\((https?://[^)]+)\)", r"\1", line)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    return cleaned.strip()


def _extract_prose_paragraphs(text: str) -> List[List[str]]:
    """Splits answer text into prose paragraphs and sentences, excluding URL citation blocks."""
    paragraphs: List[List[str]] = []
    current_lines: List[str] = []
    in_citations_section = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if re.match(r"^(?:\*\*)?citations?\s*:?(?:\*\*)?$", stripped, re.IGNORECASE):
            in_citations_section = True
            continue
        if in_citations_section:
            continue
        if re.match(r"^\[\d+\]\s+https?://", stripped):
            continue

        if not stripped:
            if current_lines:
                para_text = " ".join(current_lines)
                sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para_text) if s.strip()]
                if sents:
                    paragraphs.append(sents)
                current_lines = []
        else:
            cleaned = _clean_prose_line(stripped)
            cleaned = re.sub(r"^[*#>\-\s]+(?:\*\*|__)?", "", cleaned).strip()
            if cleaned:
                current_lines.append(cleaned)

    if current_lines:
        para_text = " ".join(current_lines)
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para_text) if s.strip()]
        if sents:
            paragraphs.append(sents)

    return paragraphs


def _split_clauses(sentence: str) -> List[str]:
    """Splits a sentence into semantic clauses across contrast/conjunction boundaries."""
    parts = re.split(
        r";\s*|\s+[—–]\s+|\s*,?\s+\b(?:but|however|whereas|while|although|yet)\b\s*,?\s*",
        sentence,
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if p and p.strip()]


def _find_clause_competitors(clause_lower: str) -> List[str]:
    found: List[str] = []
    for comp in KNOWN_COMPETITORS:
        if re.search(rf"\b{re.escape(comp)}\b", clause_lower) and comp not in found:
            found.append(comp)
    return found


def _is_prompt_echo_only(sentence: str) -> bool:
    """
    Returns True when a sentence merely recaps or quotes a user query about Kasparro
    rather than discussing or evaluating the brand itself.
    """
    if not re.search(r"\bkasparro\b", sentence, re.IGNORECASE):
        return False

    s = sentence.strip()
    is_echo_framed = bool(PROMPT_ECHO_PREFIX_RE.search(s) or PROMPT_LABEL_PREFIX_RE.search(s))
    if not is_echo_framed:
        # Pure quoted question without evaluative frame (e.g. '"What is Kasparro?"')
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return True
        return False

    # If sentence repeats an indirect question ("asked whether Kasparro works"), keep as echo.
    if ECHO_INDIRECT_QUESTION_RE.search(s):
        return True

    # Strip quoted portions to inspect whether the non-quoted remainder evaluates Kasparro.
    unquoted = re.sub(r"[\"'][^\"']*[\"']", " ", s)
    if not re.search(r"\bkasparro\b", unquoted, re.IGNORECASE):
        # Kasparro appeared solely inside the quoted prompt/recap.
        return True

    if EVALUATIVE_POST_KASPARRO_RE.search(unquoted):
        return False

    return True


def _collect_target_clauses(paragraphs: List[List[str]]) -> Tuple[bool, List[Tuple[str, bool]]]:
    """
    Identifies genuine Kasparro discussion and collects (clause_text, is_anaphor) tuples
    scoped strictly to Kasparro (direct mentions or unambiguous same-paragraph continuations).
    """
    has_genuine_mention = False
    target_clauses: List[Tuple[str, bool]] = []

    for para in paragraphs:
        active_focus: Optional[str] = None
        for sentence in para:
            if _is_prompt_echo_only(sentence):
                active_focus = None
                continue

            clauses = _split_clauses(sentence)
            sentence_has_kasparro = bool(re.search(r"\bkasparro\b", sentence, re.IGNORECASE))
            if sentence_has_kasparro:
                has_genuine_mention = True

            for clause in clauses:
                cl_lower = clause.lower()
                has_k = bool(re.search(r"\bkasparro\b", cl_lower))
                comps = _find_clause_competitors(cl_lower)

                if has_k:
                    target_clauses.append((clause, False))
                    if not comps:
                        active_focus = "kasparro"
                    else:
                        # Ambiguous multi-brand clause resets pronoun carry-over unless Kasparro is sole subject
                        active_focus = "kasparro" if cl_lower.lstrip("* ").startswith("kasparro") and "over kasparro" not in cl_lower else None
                elif comps:
                    active_focus = "competitor"
                elif INDUSTRY_SUBJECT_RE.search(cl_lower):
                    active_focus = "industry"
                elif active_focus == "kasparro" and PRONOUN_REF_RE.search(cl_lower):
                    target_clauses.append((clause, True))

    return has_genuine_mention, target_clauses


def _evaluate_recommendation(target_clauses: List[Tuple[str, bool]]) -> bool:
    """Determines whether any clause in Kasparro's contextual window expresses a recommendation for Kasparro."""
    for clause, is_anaphor in target_clauses:
        cl_lower = clause.lower()
        comps = _find_clause_competitors(cl_lower)

        # Skip passive descriptions of AI recommendation mechanics ("represented, recommended, or omitted")
        if re.search(r"\b(?:recommended|mentioned)\s*,?\s+or\s+omitted\b|\bgetting\s+recommended\s+by\b", cl_lower):
            continue

        # Explicit negated recommendation in clause
        if RECOMMENDATION_NEGATION_RE.search(cl_lower):
            continue

        # Competitor comparative preference over Kasparro
        if comps:
            if re.search(r"\b(?:over|instead\s+of|rather\s+than)\s+kasparro\b|\bbetter\s+than\s+kasparro\b", cl_lower):
                continue
            comp_rec_hit = any(
                re.search(rf"\b(?:recommend(?:ed|ing|s)?|prefer|choose|pick|suggest)\b[^.;]*\b{re.escape(c)}\b", cl_lower)
                for c in comps
            )
            if comp_rec_hit and not KASPARRO_DIRECT_REC_RE.search(cl_lower) and not KASPARRO_PREDICATE_REC_RE.search(cl_lower):
                continue

        if is_anaphor:
            if ANAPHOR_REC_RE.search(cl_lower) and not REC_NEGATED_GUARD_RE.search(cl_lower):
                return True
            continue

        if KASPARRO_DIRECT_REC_RE.search(cl_lower):
            return True

        if KASPARRO_PREDICATE_REC_RE.search(cl_lower) and not REC_NEGATED_GUARD_RE.search(cl_lower):
            return True

        if GENERAL_IMPROVEMENT_REC_RE.search(cl_lower) and not REC_NEGATED_GUARD_RE.search(cl_lower):
            return True

    return False


def _evaluate_negativity(target_clauses: List[Tuple[str, bool]]) -> bool:
    """Determines whether any clause directed at Kasparro expresses negative characterization."""
    for clause, _ in target_clauses:
        cl_lower = clause.lower()
        comps = _find_clause_competitors(cl_lower)

        # Comparative preference or competitor-subject clauses do not automatically taint Kasparro
        if comps and re.search(r"\b(?:over|instead\s+of|rather\s+than)\s+kasparro\b", cl_lower):
            if not any(
                re.search(r"\bkasparro\b[^.;]*\b(?:unreliable|unproven|scam|lacks?|poor)\b", cl_lower)
                for _ in (0,)
            ):
                continue

        # Neutral lack-of-information / inability-to-verify is neutral unless explicit warning is present
        if NEUTRAL_UNCERTAINTY_RE.search(cl_lower):
            has_explicit_warning = bool(
                re.search(r"\b(?:scam|unproven|unreliable|exercise\s+caution|not\s+recommended)\b", cl_lower)
            )
            if not has_explicit_warning:
                continue

        # Negated negative labels ("neither a complete scam", "not unreliable")
        if NEGATIVE_NEGATED_GUARD_RE.search(cl_lower):
            continue

        # Check explicit negative characterization patterns
        for pat in KASPARRO_NEGATIVE_PATTERNS:
            if pat.search(cl_lower):
                # If a competitor is also in the clause, confirm competitor isn't the sole negative subject
                if comps:
                    comp_is_subject = any(
                        re.search(rf"\b{re.escape(c)}\b[^.;]*{pat.pattern}", cl_lower)
                        for c in comps
                    )
                    kasparro_is_subject = bool(
                        re.search(rf"\bkasparro\b[^.;]*{pat.pattern}", cl_lower)
                    )
                    if comp_is_subject and not kasparro_is_subject:
                        continue
                return True

    return False


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

        paragraphs = _extract_prose_paragraphs(answer_text)
        has_mention, target_clauses = _collect_target_clauses(paragraphs)
        competitors = self._find_competitors(answer_text.lower())

        if not has_mention:
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="success",
                kasparro_absent=True,
                kasparro_mentioned=False,
                kasparro_recommended=False,
                kasparro_negative=False,
                competitors=competitors,
                recommendation_position=None,
                evidence=[],
                confidence=1.0,
                execution_mode="replay",
                classifier_version=self.classifier_version,
            )

        is_recommended = _evaluate_recommendation(target_clauses)
        is_negative = _evaluate_negativity(target_clauses)
        evidence_items = self._extract_evidence(answer_text)
        position = self._extract_position(answer_text)

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
        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        for s in sentences:
            s_clean = s.strip()
            if "kasparro" in s_clean.lower() and len(s_clean) > 10:
                if _is_prompt_echo_only(_clean_prose_line(s_clean)):
                    continue
                sub = s_clean[:250].strip()
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
