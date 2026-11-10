import copy
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Tuple, Optional, List, Dict, Set, Any, Mapping


def locate_evidence(excerpt: str, source_text: str) -> Tuple[bool, Optional[str], Optional[int], Optional[int]]:
    """
    Locate an evidence excerpt as an exact substring of its source.

    Whitespace normalization is deliberately not allowed: offsets must point to
    the exact characters shown in the report.
    """
    if not isinstance(excerpt, str) or not excerpt:
        return False, "empty_evidence", None, None
    if not isinstance(source_text, str) or not source_text:
        return False, "empty_source", None, None

    start = source_text.find(excerpt)
    if start < 0:
        return False, "non_verbatim", None, None

    return True, None, start, start + len(excerpt)


def validate_evidence(excerpt: str, source_text: str) -> Tuple[bool, Optional[str]]:
    """Backward-compatible exact-match validator."""
    is_valid, reason, _, _ = locate_evidence(excerpt, source_text)
    if is_valid:
        return True, None
    messages = {
        "empty_evidence": "Evidence excerpt is empty",
        "empty_source": "Source text is empty",
        "non_verbatim": f"Excerpt '{excerpt[:50]}...' not found exactly in source text.",
    }
    return False, messages.get(reason, "Evidence validation failed")


def _excerpt_kind(excerpt: str) -> str:
    """Label fragments honestly; do not imply every exact excerpt is a full sentence."""
    return "complete_sentence" if re.search(r'[.!?][\"\'’”)}\\]]*$', excerpt.rstrip()) else "verbatim_fragment"


def enrich_diagnostic_evidence(
    diagnostics: List[Dict[str, Any]],
    source_text_by_response_id: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """
    Return a copy of diagnostics with verified source offsets.

    Raises ValueError instead of allowing a report with missing, mismatched,
    or duplicated evidence to be created, submitted, or exported.
    """
    enriched = copy.deepcopy(diagnostics)
    for diagnostic_index, diagnostic in enumerate(enriched):
        title = diagnostic.get("title", f"diagnostic_{diagnostic_index + 1}")
        evidence_items = diagnostic.get("evidence", [])
        if not isinstance(evidence_items, list):
            raise ValueError(f"Diagnostic '{title}' evidence must be a list")

        seen = set()
        for evidence_index, item in enumerate(evidence_items):
            if not isinstance(item, dict):
                raise ValueError(f"Diagnostic '{title}' evidence item {evidence_index + 1} must be an object")

            response_id = item.get("response_id")
            excerpt = item.get("excerpt")
            if not response_id:
                raise ValueError(f"Diagnostic '{title}' evidence item {evidence_index + 1} has no response_id")
            source_text = source_text_by_response_id.get(response_id)
            if source_text is None:
                raise ValueError(f"Diagnostic '{title}' references unknown response_id '{response_id}'")

            is_valid, reason, start, end = locate_evidence(excerpt, source_text)
            if not is_valid:
                raise ValueError(
                    f"Diagnostic '{title}' evidence for response '{response_id}' failed validation: {reason}"
                )

            occurrence = (response_id, start, end)
            if occurrence in seen:
                raise ValueError(
                    f"Diagnostic '{title}' contains duplicate evidence for response '{response_id}'"
                )
            seen.add(occurrence)

            item["start_offset"] = start
            item["end_offset"] = end
            item["validation_status"] = "verified"
            item["excerpt_kind"] = _excerpt_kind(excerpt)

    return enriched


TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source"
}


def normalize_url(raw_url: str) -> str:
    """
    Normalizes a citation URL:
    - Lowercases scheme and host
    - Strips fragment (#)
    - Strips common analytics/tracking query params
    - Strips trailing slash on root paths
    """
    if not raw_url:
        return ""

    parsed = urlparse(raw_url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    query_items = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_queries = [(k, v) for k, v in query_items if k.lower() not in TRACKING_PARAMS]
    new_query = urlencode(filtered_queries)

    path = parsed.path
    if path == "/" or not path:
        path = ""
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", new_query, ""))


def aggregate_citations(citations: List[Dict[str, str]]) -> Dict[str, Any]:
    """Computes occurrences vs unique normalized URLs."""
    total_occurrences = len(citations)
    unique_normalized: Set[str] = set()

    for citation in citations:
        url = citation.get("url")
        if url:
            normalized = normalize_url(url)
            if normalized:
                unique_normalized.add(normalized)

    return {
        "total_occurrences": total_occurrences,
        "unique_normalized_count": len(unique_normalized),
        "unique_urls": sorted(unique_normalized),
    }
