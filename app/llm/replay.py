import re
from typing import Any, Dict, List, Optional, Tuple
from app.llm.base import LLMBase, ClassificationResult, EvidenceItem

MAX_EVIDENCE_EXCERPT_CHARS = 360

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

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "for", "of", "to", "and", "or", "with", "about",
    "regarding", "as", "by", "from", "that", "this", "these", "those",
    "it", "its", "what", "which", "who", "whom", "how", "why", "when",
    "where", "whether", "if", "do", "does", "did", "can", "could",
    "would", "should", "will", "user", "submitted", "prompt", "query",
    "question", "asked", "me", "you", "your", "tell",
}

ASPECT_BULLET_PREFIX_RE = re.compile(
    r"^(?:pros|cons|strengths|weaknesses|limitations?|caveats?|verdict|"
    r"pricing|overview|features?|summary|recommendation|notes?|evidence)\s*[:\-]",
    re.IGNORECASE,
)

PROMPT_ECHO_PREFIX_RE = re.compile(
    r"^(?:in\s+(?:response|reply)\s+to\s+|based\s+on\s+)?"
    r"(?:the\s+user|you|your|this\s+(?:prompt|query|question)|the\s+(?:prompt|query|question))\b"
    r"[^.!?]*\b(?:ask(?:ed|ing)?|submit(?:ted)?|mention(?:ed)?|referenc(?:ed|ing)|"
    r"inquir(?:ed|ing)|quer(?:y|ied)|search(?:ed)?|regarding|about)\b",
    re.IGNORECASE,
)

PROMPT_LABEL_PREFIX_RE = re.compile(
    r"^(?:user\s+)?(?:prompt|query|question|topic|subject)\s*[:\-]\s*",
    re.IGNORECASE,
)

EVALUATIVE_POST_KASPARRO_RE = re.compile(
    r"\bkasparro\b(?:\s*\([^)]*\))?\s+"
    r"(?:is|are|was|were|offers?|provides?|tracks?|helps?|competes?|lacks?|positions?|remains?|stands|serves|"
    r"delivers?|features?|supports?|deserves?|requires?|can|may|should|could|will|would|seems?|appears?)\b",
    re.IGNORECASE,
)

ECHO_INDIRECT_QUESTION_RE = re.compile(
    r"\b(?:ask(?:ed|ing)?|inquir(?:ed|ing)|question(?:ed|ing)?|wonder(?:ed|ing)?)\s+(?:whether|if)\b",
    re.IGNORECASE,
)

RECOMMENDATION_NEGATION_RE = re.compile(
    r"\b(?:not|never|cannot|can't|couldn't|wouldn't|would\s+not|do\s+not|don't|"
    r"hard\s+to|hesitate\s+to|should\s+not|shouldn't|decline\s+to)\s+"
    r"(?:be\s+)?(?:strongly\s+|highly\s+|widely\s+)?recommend(?:ed|ing|able|s)?\b"
    r"|\b(?:cannot|can't|would\s+not|wouldn't|do\s+not|don't)\s+endorse\b"
    r"|\badvise\s+against\b"
    r"|\b(?:not|never|hardly|scarcely|far\s+from)\s+(?:a\s+)?(?:being\s+)?(?:a\s+)?"
    r"(?:good|great|top|strong|suitable|viable|solid|ideal|practical|recommended)\s+"
    r"(?:choice|pick|option|tool|platform|solution|agency|fit|contender)\b"
    r"|\b(?:not|never)\s+(?:well[- ]suited|better\s+suited|recommended|worth\s+(?:considering|evaluating|trying|shortlisting))\b",
    re.IGNORECASE,
)

KASPARRO_DIRECT_REC_RE = re.compile(
    r"\b(?:recommend(?:ed|ing|s)?|endorse(?:d|s|ing)?|shortlist(?:ed|ing|s)?|"
    r"suggest(?:s|ed|ing)?|choose|pick|select|go\s+with|opt\s+for)\s+"
    r"(?:trying\s+|using\s+|evaluating\s+|testing\s+|adopting\s+|shortlisting\s+)?kasparro\b",
    re.IGNORECASE,
)

KASPARRO_PREDICATE_REC_RE = re.compile(
    r"\bkasparro\b[^.;]*\b(?:is|are|stands\s+out\s+as|serves\s+as|positions\s+itself\s+as|"
    r"remains|could\s+be|may\s+be|might\s+be|appears\s+to\s+be|seems\s+to\s+be|makes\s+for)\b"
    r"[^.;]*\b(?:strong\s+(?:contender|(?:ai\s+\w+\s+)?platform|option|tool|choice|fit|pick)|"
    r"(?:good|great|solid|ideal|practical|compelling)\s+(?:choice|option|tool|fit|platform|solution)|"
    r"top\s+(?:choice|pick|option|tool|agency|platform)|"
    r"(?:one\s+of\s+the\s+)?(?:best|top|leading|standout|preferred)\s+(?:tools?|platforms?|options?|choices?|solutions?|picks?)|"
    r"suitable\s+option|viable\s+(?:option|choice|solution|tool|provider)|"
    r"recommended(?:\s+(?:option|tool|platform|choice|solution))?|"
    r"well[- ]suited\s+(?:to|for)|better\s+suited\s+(?:to|for)|"
    r"more\s+(?:practical|accessible|cost[- ]effective|suitable|affordable)\b[^.;]*\bthan|"
    r"worth\s+(?:considering|evaluating|trying|shortlisting))\b"
    r"|\bkasparro\b[^.;]*\bworth\s+(?:considering|evaluating|trying|shortlisting)\b"
    r"|\bkasparro\b[^.;]*\b(?:is|are|remains)\s+(?:(?:highly|strongly|widely|frequently|often|broadly|generally)\s+)?recommended\b"
    r"|\bkasparro\b[^.;]*\b(?:well[- ]suited|better\s+suited)\s+(?:to|for)\b"
    r"|\bkasparro\b[^.;]*\b(?:a\s+)?(?:good|strong|great|ideal|solid)\s+fit\s+for\b"
    r"|\bkasparro\b[^.;]*\bstands\s+out\s+(?:for|as)\b",
    re.IGNORECASE,
)

ANAPHOR_REC_RE = re.compile(
    r"\b(?:works?\s+well|"
    r"(?:is|are|remains|could\s+be|may\s+be)\s+(?:a\s+)?(?:strong\s+contender|good\s+choice|"
    r"viable\s+option|solid\s+(?:choice|option|tool|platform)|(?:good|strong|great|ideal)\s+fit|"
    r"one\s+of\s+the\s+(?:best|top|leading)\s+(?:tools?|platforms?|options?|choices?)|"
    r"well[- ]suited\s+(?:to|for)|better\s+suited\s+(?:to|for)|"
    r"(?:(?:highly|strongly|widely|frequently|often)\s+)?recommended)|"
    r"worth\s+(?:considering|evaluating|trying|shortlisting)|"
    r"provides?\s+much-needed\s+visibility|see\s+measurable\s+improvements)\b",
    re.IGNORECASE,
)

GENERAL_IMPROVEMENT_REC_RE = re.compile(
    r"\b(?:works?\s+well|measurable\s+improvements)\b",
    re.IGNORECASE,
)

REC_NEGATED_GUARD_RE = re.compile(
    r"\b(?:couldn't\s+find|could\s+not\s+find|would\s+not\s+expect|no\s+(?:independent\s+)?evidence\s+that|"
    r"unlikely\s+to\s+be\s+worth|not\s+clear\s+whether\s+it\s+is\s+worth)\b",
    re.IGNORECASE,
)

AI_ENGINE_REC_MECHANICS_RE = re.compile(
    r"\b(?:recommended|mentioned)\s*,?\s+or\s+omitted\b"
    r"|\bgetting\s+recommended\s+by\b"
    r"|\brecommended\s+by\s+(?:ai\b|llms?\b|chatgpt\b|gemini\b|claude\b|perplexity\b|search\s+engines?\b|models?\b)",
    re.IGNORECASE,
)

NEUTRAL_UNCERTAINTY_RE = re.compile(
    r"\b(?:insufficient\s+(?:public\s+)?(?:information|data|evidence)\s+to\s+(?:assess|evaluate|judge|determine|rate|verify)|"
    r"(?:not\s+enough|limited)\s+(?:verified|public)\s+(?:information|data|details|info)\s+(?:is\s+available\s+)?to\s+(?:assess|evaluate|judge|determine|verify)|"
    r"there\s+(?:isn't|is\s+not)\s+enough\s+(?:public\s+|verified\s+)?(?:info|information|data|details)\s+to\s+(?:assess|evaluate|judge|determine|verify)|"
    r"(?:couldn't|could\s+not|unable\s+to)\s+find\s+(?:reliable\s+public\s+pricing|enough\s+(?:public\s+|verified\s+)?(?:info|information|data|details)\s+to\s+(?:assess|evaluate|judge|determine))|"
    r"no\s+public\s+pricing\s+(?:available|listed))\b",
    re.IGNORECASE,
)

# Negative-trait patterns (subject to prefix negation / double-negation checks)
NEGATIVE_TRAIT_PATTERNS = [
    re.compile(r"\bunreliable\b|\bunproven\b|\bquestionable\b|\buntrustworthy\b|\bunverified\b|\bfraudulent\b|\bdubious\b", re.IGNORECASE),
    re.compile(r"\bscam(?:adviser)?\b|\bred\s+flags?\b|\bwarning\s+signs?\b", re.IGNORECASE),
    re.compile(r"\b(?:exercise|advise|urge)\s+caution\b|\breasons?\s+to\s+be\s+cautious\b|\bapproach\s+with\s+caution\b|\bavoid\s+(?:using\s+)?kasparro\b", re.IGNORECASE),
    re.compile(r"\bnegative\s+reviews?\b|\bpoor\s+(?:evidence|reviews?|track\s+record|reputation|reliability|accuracy)\b", re.IGNORECASE),
]

# Negative-by-absence / explicit anti-recommendation patterns
NEGATIVE_ABSENCE_OR_REJECTION_PATTERNS = [
    re.compile(r"\b(?:not|never|cannot|can't|couldn't|wouldn't|would\s+not|do\s+not|don't|should\s+not|shouldn't)\s+(?:be\s+)?recommend(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:a\s+)?widely\s+recognized\b", re.IGNORECASE),
    re.compile(r"\blacks?\s+(?:independent\s+|verifiable\s+|credible\s+|proven\s+|public\s+)?(?:case\s+studies|evidence|validation|proof|track\s+record|reviews?)\b", re.IGNORECASE),
    re.compile(r"\b(?:couldn't|could\s+not)\s+find\s+(?:independent|verifiable|third[- ]party)\s+(?:evidence|case\s+studies|data|proof|reviews?)\b", re.IGNORECASE),
    re.compile(r"\bthere\s+(?:isn't|is\s+not|are\s+very\s+few|are\s+no)\s+(?:much\s+)?(?:independent\s+|verifiable\s+)?(?:evidence|case\s+studies|reviews?|validation|proof)\b", re.IGNORECASE),
    re.compile(r"\b(?:limited|no|little)\s+independent\s+(?:validation|evidence|case\s+studies|data|reviews?|verification|proof)\b", re.IGNORECASE),
    re.compile(r"\bwould\s+not\s+expect\b[^.;]*\breliably\b", re.IGNORECASE),
]

TRAIT_PREFIX_NEGATION_RE = re.compile(
    r"(?:"
    r"\bno\s+(?:credible\s+|solid\s+|verified\s+)?evidence\s+(?:that|to\s+suggest|of)\s+[^.;]{0,55}"
    r"|\bthere\s+(?:is|are)\s+no\s+(?:credible\s+|major\s+|clear\s+)?(?:evidence\s+that\s+[^.;]{0,45}|signs?\s+of\s+)?"
    r"|\b(?:unfair|inaccurate|wrong|misleading|incorrect)\s+to\s+(?:describe|call|label|dismiss|characterize)\s+[^.;]{0,45}"
    r"|\b(?:not|never|hardly|scarcely|neither|nor|without\s+being|far\s+from|free\s+of|absence\s+of)\s+(?:(?:a|an|any|being|accurately\s+described\s+as)\s+)*"
    r"|\b(?:not|no)\s+(?:major\s+|clear\s+|obvious\s+)?"
    r")$",
    re.IGNORECASE,
)

PRONOUN_REF_RE = re.compile(
    r"^(?:\*+\s*)?(?:(?:however|still|nevertheless|additionally|furthermore|overall|"
    r"fortunately|unfortunately|specifically|that\s+said|in\s+practice),?\s+)?"
    r"(?:where\s+it|it|its|it's|they|their|this\s+(?:platform|tool|company|product|service|vendor|solution)|"
    r"the\s+(?:platform|tool|company|product|service|vendor|solution))\b",
    re.IGNORECASE,
)

INDUSTRY_SUBJECT_RE = re.compile(
    r"\b(?:ai\s+visibility\s+(?:tracking|tools|platforms)|llms?|large\s+language\s+models?|"
    r"many\s+(?:basic\s+)?(?:tools|trackers|platforms)|most\s+agencies)\b",
    re.IGNORECASE,
)

OTHER_SUBJECT_RE = re.compile(
    r"\b(?:other\s+(?:tools?|platforms?|vendors?|solutions?|providers?|options?|competitors?)|"
    r"competitors?|alternatives?|both\s+(?:tools?|platforms?|options?|solutions?)|"
    r"all\s+(?:of\s+)?these\s+(?:tools?|platforms?|options?)|several\s+(?:tools?|platforms?|options?)|"
    r"many\s+(?:tools?|platforms?|users?|agencies|teams?|buyers?)|"
    r"most\s+(?:tools?|platforms?|agencies|buyers?)|reviewers?|critics?)\b",
    re.IGNORECASE,
)

UNLISTED_ENTITY_SUBJECT_RE = re.compile(
    r"^(?:however,?\s+|additionally,?\s+|meanwhile,?\s+|in\s+contrast,?\s+)?"
    r"(?!(?:Kasparro|This|That|These|Those|It|Its|They|Their|There|Here|Some|Many|Most|Several|"
    r"Both|All|One|While|Although|Though|Because|Since|When|Where|If|Overall|Summary|"
    r"Conclusion|Note|Users|Teams|Buyers|Analysts|Experts|Reviewers|Practitioners)\b)"
    r"([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)\s+"
    r"(?:is|are|was|were|offers?|has|have|provides?|leads?|outperforms?|competes?|focuses?|tracks?|stands|ranks?)\b"
)


def _clean_prose_line(line: str) -> str:
    """Removes Markdown URL targets and raw URLs so slugs do not distort prose matching."""
    # Ensure inline citations immediately following punctuation don't glue next word onto punctuation
    cleaned = re.sub(r"(?<=[.!?])\[([^\]]+)\]\((https?://[^)]+)\)", r" \1", line)
    cleaned = re.sub(r"\[([^\]]*)\]\((https?://[^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    return cleaned.strip()


def _split_prose_sentences(para_text: str) -> List[str]:
    """Splits a paragraph into sentences without breaking common abbreviations."""
    parts = re.split(r"(?<!e\.g)(?<!i\.e)(?<!\bvs)(?<=[.!?])\s+", para_text)
    return [s.strip() for s in parts if s and s.strip()]


def _extract_prose_paragraphs(text: str) -> List[List[str]]:
    """Splits answer text into prose paragraphs and sentences, excluding URL citation blocks."""
    paragraphs: List[List[str]] = []
    current_lines: List[str] = []
    in_citations_section = False

    def flush_paragraph() -> None:
        nonlocal current_lines
        if current_lines:
            para_text = " ".join(current_lines)
            sents = _split_prose_sentences(para_text)
            if sents:
                paragraphs.append(sents)
            current_lines = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if re.match(r"^(?:\*\*)?citations?\s*:?(?:\*\*)?$", stripped, re.IGNORECASE):
            in_citations_section = True
            flush_paragraph()
            continue
        if in_citations_section:
            continue
        if re.match(r"^\[\d+\]\s+https?://", stripped):
            continue

        if not stripped:
            flush_paragraph()
            continue

        # New markdown heading or numbered item starts a clean paragraph focus boundary
        is_heading = bool(re.match(r"^#{1,6}\s+", stripped))
        is_numbered = bool(re.match(r"^\d+[\.\)]\s+", stripped))
        is_bullet = bool(re.match(r"^[-*+•]\s+", stripped))

        brand_bullet_match = re.match(
            r"^[-*+•]\s+(?:\*\*|__)?([A-Za-z][A-Za-z0-9 .-]{1,40}?)(?:\*\*|__)?\s*[:—–-]\s+",
            stripped,
        )
        is_new_brand_bullet = bool(
            brand_bullet_match and not ASPECT_BULLET_PREFIX_RE.match(brand_bullet_match.group(1).strip() + ":")
        )

        if is_heading or is_numbered or is_new_brand_bullet:
            flush_paragraph()

        cleaned = _clean_prose_line(stripped)
        if is_numbered:
            cleaned = re.sub(r"^\d+[\.\)]\s+", "", cleaned).strip()
        cleaned = re.sub(r"^[*#>\-•\s]+(?:\*\*|__)?", "", cleaned).strip()

        if cleaned:
            if is_bullet and current_lines and not is_new_brand_bullet:
                # Keep bullet within same parent paragraph but isolate as distinct sentence if previous lacked punctuation
                prev = current_lines[-1]
                if prev and prev[-1] not in ".!?":
                    current_lines[-1] = prev + "."
            current_lines.append(cleaned)

        if is_heading:
            flush_paragraph()

    flush_paragraph()
    return paragraphs


def _split_clauses(sentence: str) -> List[str]:
    """Splits a sentence into semantic clauses across contrast/conjunction boundaries."""
    parts = re.split(
        r";\s*|\s+[—–]\s+|\s*,?\s+\b(?:but|however|whereas|while|although|yet|though)\b\s*,?\s*",
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


def _content_tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in STOPWORDS]


def _is_prompt_echo_only(sentence: str, prompt_text: Optional[str] = None) -> bool:
    """
    Returns True when a sentence merely recaps or quotes a user query about Kasparro
    rather than discussing or evaluating the brand itself.
    """
    if not re.search(r"\bkasparro\b", sentence, re.IGNORECASE):
        return False

    s = sentence.strip()
    unquoted = re.sub(r"[\"'][^\"']*[\"']", " ", s)

    # Check direct/near-literal repetition against known original prompt_text
    if prompt_text and re.search(r"\bkasparro\b", prompt_text, re.IGNORECASE):
        norm_s = re.sub(r"^[\"'`]+|[\"'`]+$", "", PROMPT_LABEL_PREFIX_RE.sub("", s)).strip()
        norm_p = re.sub(r"^[\"'`]+|[\"'`]+$", "", prompt_text.strip()).strip()
        if norm_s.lower().rstrip("?.!:") == norm_p.lower().rstrip("?.!:"):
            return True

        p_tokens = set(_content_tokens(norm_p))
        s_tokens = _content_tokens(norm_s)
        if p_tokens and s_tokens:
            overlap_ratio = len(set(s_tokens) & p_tokens) / max(len(set(s_tokens)), 1)
            extra_tokens = set(s_tokens) - p_tokens
            if (norm_s.endswith("?") or PROMPT_ECHO_PREFIX_RE.search(s) or PROMPT_LABEL_PREFIX_RE.search(s)):
                if overlap_ratio >= 0.75 and len(extra_tokens) <= 1 and not EVALUATIVE_POST_KASPARRO_RE.search(unquoted):
                    return True

    is_echo_framed = bool(PROMPT_ECHO_PREFIX_RE.search(s) or PROMPT_LABEL_PREFIX_RE.search(s))
    if not is_echo_framed:
        # Pure quoted question without evaluative frame (e.g. '"What is Kasparro?"')
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return True
        return False

    # Inspect independent remainder after stripping echo framing / indirect prompt clause
    remainder = PROMPT_LABEL_PREFIX_RE.sub("", unquoted).strip()
    remainder = re.sub(
        r"^(?:in\s+(?:response|reply)\s+to\s+|based\s+on\s+)?"
        r"(?:the\s+user|you|your|this\s+(?:prompt|query|question)|the\s+(?:prompt|query|question))"
        r"[^.;:?!]*?(?:[,;:]|\band\b|\bbut\b|\bhowever\b|$)",
        "",
        remainder,
        flags=re.IGNORECASE,
    ).strip()

    if not re.search(r"\bkasparro\b", remainder, re.IGNORECASE):
        # Kasparro appeared only inside the prompt/question recap portion
        return True

    if ECHO_INDIRECT_QUESTION_RE.search(s) and not EVALUATIVE_POST_KASPARRO_RE.search(remainder):
        return True

    if EVALUATIVE_POST_KASPARRO_RE.search(remainder):
        return False

    return True


def _collect_target_clauses(
    paragraphs: List[List[str]],
    prompt_text: Optional[str] = None,
) -> Tuple[bool, List[Tuple[str, bool]]]:
    """
    Identifies genuine Kasparro discussion and collects (clause_text, is_anaphor) tuples
    scoped strictly to Kasparro (direct mentions or unambiguous same-paragraph continuations).
    """
    has_genuine_mention = False
    target_clauses: List[Tuple[str, bool]] = []

    for para in paragraphs:
        active_focus: Optional[str] = None
        for sentence in para:
            if _is_prompt_echo_only(sentence, prompt_text=prompt_text):
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
                    if not comps and not OTHER_SUBJECT_RE.search(cl_lower):
                        active_focus = "kasparro"
                    else:
                        # Ambiguous multi-entity comparison/co-mention resets pronoun carry-over
                        active_focus = None
                elif comps:
                    active_focus = "competitor"
                elif INDUSTRY_SUBJECT_RE.search(cl_lower):
                    active_focus = "industry"
                elif OTHER_SUBJECT_RE.search(cl_lower) or UNLISTED_ENTITY_SUBJECT_RE.search(clause.strip()):
                    active_focus = "other"
                elif active_focus == "kasparro" and (
                    PRONOUN_REF_RE.search(cl_lower) or ASPECT_BULLET_PREFIX_RE.match(cl_lower.strip())
                ):
                    target_clauses.append((clause, True))

    return has_genuine_mention, target_clauses


def _closest_entity_is_competitor(cl_lower: str, comps: List[str], match_start: int) -> bool:
    """Returns True when a competitor is grammatically closer to a predicate than Kasparro."""
    if not comps:
        return False
    prefix = cl_lower[:match_start]
    last_k = max((m.end() for m in re.finditer(r"\bkasparro\b", prefix)), default=-1)
    last_c = max(
        (m.end() for c in comps for m in re.finditer(rf"\b{re.escape(c)}\b", prefix)),
        default=-1,
    )
    if last_c > last_k:
        # Check if Kasparro wasn't explicitly made subject right before the predicate
        return True
    if last_k == -1 and last_c == -1:
        # Entities appear after predicate (e.g. "Unlike Kasparro, ...")
        return True
    return False


def _evaluate_recommendation(target_clauses: List[Tuple[str, bool]]) -> bool:
    """Determines whether any clause in Kasparro's contextual window expresses a recommendation for Kasparro."""
    for clause, is_anaphor in target_clauses:
        cl_lower = clause.lower()
        comps = _find_clause_competitors(cl_lower)

        # Skip passive descriptions of AI recommendation mechanics ("represented, recommended, or omitted")
        if AI_ENGINE_REC_MECHANICS_RE.search(cl_lower):
            continue

        # Explicit negated recommendation in clause
        if RECOMMENDATION_NEGATION_RE.search(cl_lower):
            continue

        # Competitor comparative preference over Kasparro
        if comps:
            if re.search(
                r"\b(?:over|instead\s+of|rather\s+than)\s+kasparro\b"
                r"|\b(?:better|more\s+suitable|more\s+reliable)\s+than\s+kasparro\b"
                r"|\boutperforms?\s+kasparro\b",
                cl_lower,
            ):
                continue
            comp_rec_hit = any(
                re.search(
                    rf"\b(?:recommend(?:ed|ing|s)?|prefer|choose|pick|suggest|endorse)\b[^.;]*\b{re.escape(c)}\b",
                    cl_lower,
                )
                for c in comps
            )
            if comp_rec_hit and not KASPARRO_DIRECT_REC_RE.search(cl_lower):
                continue

        if is_anaphor:
            if ANAPHOR_REC_RE.search(cl_lower) and not REC_NEGATED_GUARD_RE.search(cl_lower):
                return True
            continue

        if KASPARRO_DIRECT_REC_RE.search(cl_lower):
            return True

        m_pred = KASPARRO_PREDICATE_REC_RE.search(cl_lower)
        if m_pred and not REC_NEGATED_GUARD_RE.search(cl_lower):
            kasparro_deprecated = bool(
                re.search(
                    r"\b(?:unlike|over|instead\s+of|rather\s+than|than)\s+kasparro\b",
                    cl_lower[: m_pred.start() + 10],
                )
            )
            span_text = m_pred.group(0)
            comp_owns_span = any(
                re.search(rf"\b{re.escape(c)}\b", span_text)
                and not re.search(rf"\b(?:unlike|over|instead\s+of|rather\s+than|than)\s+{re.escape(c)}\b", span_text)
                for c in comps
            )
            if not kasparro_deprecated and not comp_owns_span:
                return True

        m_imp = GENERAL_IMPROVEMENT_REC_RE.search(cl_lower)
        if m_imp and not REC_NEGATED_GUARD_RE.search(cl_lower):
            if not _closest_entity_is_competitor(cl_lower, comps, m_imp.start()):
                return True

    return False


def _evaluate_negativity(target_clauses: List[Tuple[str, bool]]) -> bool:
    """Determines whether any clause directed at Kasparro expresses negative characterization."""
    for clause, _ in target_clauses:
        cl_lower = clause.lower()
        comps = _find_clause_competitors(cl_lower)

        # Subjunctive hypothetical counterfactuals are not negative assertions against Kasparro
        if re.search(r"\bif\s+(?:kasparro\s+were|a\s+(?:vendor|tool|platform)\s+were)\b", cl_lower):
            continue

        # Comparative preference clauses without negative attacks against Kasparro do not mark Kasparro negative
        if comps and re.search(r"\b(?:over|instead\s+of|rather\s+than)\s+kasparro\b", cl_lower):
            if not re.search(r"\bkasparro\b[^.;]*\b(?:unreliable|unproven|scam|lacks?|poor|untrustworthy)\b", cl_lower):
                continue

        # Neutral lack-of-information / inability-to-verify is neutral unless explicit warning is present
        if NEUTRAL_UNCERTAINTY_RE.search(cl_lower):
            has_explicit_warning = bool(
                re.search(r"\b(?:scam|unproven|unreliable|untrustworthy|exercise\s+caution|not\s+recommended|red\s+flags?)\b", cl_lower)
            )
            if not has_explicit_warning:
                continue

        # 1. Check intrinsic negative traits with prefix negation / double-negation guard
        for pat in NEGATIVE_TRAIT_PATTERNS:
            for m in pat.finditer(cl_lower):
                prefix_window = cl_lower[max(0, m.start() - 75):m.start()]
                if TRAIT_PREFIX_NEGATION_RE.search(prefix_window):
                    continue
                if comps and _closest_entity_is_competitor(cl_lower, comps, m.start()):
                    continue
                return True

        # 2. Check negative-by-absence and explicit anti-recommendation patterns
        for pat in NEGATIVE_ABSENCE_OR_REJECTION_PATTERNS:
            for m in pat.finditer(cl_lower):
                if comps and _closest_entity_is_competitor(cl_lower, comps, m.start()):
                    continue
                return True

    return False


def _split_source_into_sentences_with_spans(text: str) -> List[Tuple[int, int, str]]:
    """
    Splits raw answer_text into candidate sentence slices preserving exact character spans.
    Splits cleanly on newlines and sentence boundaries (including before inline [domain](url) citations).
    """
    candidates: List[Tuple[int, int, str]] = []
    # Break at newlines OR after sentence punctuation followed by whitespace OR before markdown link citations
    split_re = re.compile(
        r"\n+|(?<!e\.g)(?<!i\.e)(?<!\bvs)(?<=[.!?])(?:\s+|(?=\[[^\]]+\]\(https?://))"
    )
    cursor = 0
    for match in split_re.finditer(text):
        seg = text[cursor:match.start()]
        stripped = seg.strip()
        if stripped:
            rel_start = seg.find(stripped)
            candidates.append((cursor + rel_start, cursor + rel_start + len(stripped), stripped))
        cursor = match.end()

    tail = text[cursor:]
    tail_stripped = tail.strip()
    if tail_stripped:
        rel_start = tail.find(tail_stripped)
        candidates.append((cursor + rel_start, cursor + rel_start + len(tail_stripped), tail_stripped))
    return candidates


def _select_complete_bounded_excerpt(
    sentence: str,
    max_chars: int = MAX_EVIDENCE_EXCERPT_CHARS,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (excerpt, skip_reason).
    Never performs blind mid-word/mid-sentence slicing: either returns the complete sentence
    within max_chars, or a complete punctuation-delimited clause within max_chars, or skips cleanly.
    """
    if len(sentence) <= max_chars:
        return sentence, None

    # Split sentence into clause pieces preserving trailing delimiter (';', ' — ', ' – ', ',')
    clause_spans: List[str] = []
    start = 0
    for m in re.finditer(r"(?:[;,.!?](?:\s+|$)|\s+[—–]\s+)", sentence):
        end = m.start() + (1 if sentence[m.start()] in ";,.!?" else 0)
        piece = sentence[start:end].strip()
        if piece:
            clause_spans.append(piece)
        start = m.end()
    tail = sentence[start:].strip()
    if tail:
        clause_spans.append(tail)

    # Prefer the shortest complete clause containing "kasparro" ending cleanly on punctuation within limit
    for piece in clause_spans:
        if "kasparro" in piece.lower() and len(piece) > 10 and len(piece) <= max_chars:
            if piece[-1] in ".!?;,":
                return piece, None

    return None, (
        f"Skipped evidence candidate: sentence length {len(sentence)} exceeds {max_chars} chars "
        "and no complete punctuation-bounded clause containing 'kasparro' fits cleanly"
    )


class ReplayClassifier(LLMBase):
    def __init__(self, classifier_version: str = "v1"):
        self.classifier_version = classifier_version
        self.last_extraction_skips: List[Dict[str, Any]] = []

    def classify(
        self,
        response_id: str,
        engine: str,
        answer_text: str,
        failure_scenario: Optional[str] = None,
        prompt_text: Optional[str] = None,
    ) -> ClassificationResult:
        self.last_extraction_skips = []

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
        has_mention, target_clauses = _collect_target_clauses(paragraphs, prompt_text=prompt_text)
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
        evidence_items = self._extract_evidence(answer_text, prompt_text=prompt_text)
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

    def _extract_evidence(
        self,
        text: str,
        prompt_text: Optional[str] = None,
    ) -> List[EvidenceItem]:
        evidence: List[EvidenceItem] = []
        for _, _, s_clean in _split_source_into_sentences_with_spans(text):
            if "kasparro" not in s_clean.lower() or len(s_clean) <= 10:
                continue
            if _is_prompt_echo_only(_clean_prose_line(s_clean), prompt_text=prompt_text):
                self.last_extraction_skips.append({
                    "reason": "Skipped prompt-echo sentence",
                    "length": len(s_clean),
                })
                continue

            bounded, skip_reason = _select_complete_bounded_excerpt(s_clean)
            if bounded is None:
                self.last_extraction_skips.append({
                    "reason": skip_reason or "Skipped un-boundable sentence",
                    "length": len(s_clean),
                })
                continue

            if bounded in text:
                evidence.append(EvidenceItem(excerpt=bounded, location="answer_text"))
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
            if re.search(rf"\b{re.escape(comp)}\b", text_lower) and comp not in found:
                found.append(comp)
        return found
