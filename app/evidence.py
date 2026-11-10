import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Tuple, Optional, List, Dict, Set, Any


def find_evidence_match(excerpt: str, source_text: str) -> Dict[str, Any]:
    """
    Locates an evidence excerpt inside source_text and returns validation metadata
    including zero-based [start_offset, end_offset) character positions.
    Supports both exact matches and whitespace-normalized matches mapped back
    to original source_text character spans.
    """
    if not isinstance(excerpt, str) or not excerpt.strip():
        return {
            "valid": False,
            "start_offset": None,
            "end_offset": None,
            "match_type": None,
            "rejection_reason": "Evidence excerpt is empty",
        }
    if not isinstance(source_text, str) or not source_text:
        return {
            "valid": False,
            "start_offset": None,
            "end_offset": None,
            "match_type": None,
            "rejection_reason": "Source text is empty",
        }

    # 1. Exact raw substring match (ensures source_text[start:end] == excerpt)
    exact_idx = source_text.find(excerpt)
    if exact_idx != -1:
        return {
            "valid": True,
            "start_offset": exact_idx,
            "end_offset": exact_idx + len(excerpt),
            "match_type": "exact",
            "rejection_reason": None,
        }

    # 2. Whitespace-normalized match mapped back to original source_text indices
    norm_chars: List[str] = []
    orig_indices: List[int] = []
    for idx, ch in enumerate(source_text):
        if ch.isspace():
            if norm_chars and norm_chars[-1] != " ":
                norm_chars.append(" ")
                orig_indices.append(idx)
        else:
            norm_chars.append(ch)
            orig_indices.append(idx)

    if norm_chars and norm_chars[-1] == " ":
        norm_chars.pop()
        orig_indices.pop()

    norm_source = "".join(norm_chars)
    norm_excerpt = re.sub(r"\s+", " ", excerpt.strip())

    norm_idx = norm_source.find(norm_excerpt)
    if norm_idx != -1 and norm_excerpt:
        orig_start = orig_indices[norm_idx]
        orig_end = orig_indices[norm_idx + len(norm_excerpt) - 1] + 1
        return {
            "valid": True,
            "start_offset": orig_start,
            "end_offset": orig_end,
            "match_type": "normalized_whitespace",
            "rejection_reason": None,
        }

    return {
        "valid": False,
        "start_offset": None,
        "end_offset": None,
        "match_type": None,
        "rejection_reason": f"Excerpt '{excerpt.strip()[:50]}...' not found verbatim in source text.",
    }


def validate_evidence(excerpt: str, source_text: str) -> Tuple[bool, Optional[str]]:
    """
    Validates that the given evidence excerpt exists verbatim in the source text.
    Rejects fabricated or hallucinated evidence.
    """
    result = find_evidence_match(excerpt, source_text)
    if result["valid"]:
        return True, None
    return False, result["rejection_reason"]


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

    # Filter out tracking query params
    query_items = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_queries = [(k, v) for k, v in query_items if k.lower() not in TRACKING_PARAMS]
    new_query = urlencode(filtered_queries)

    # Normalize path
    path = parsed.path
    if path == "/" or not path:
        path = ""
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    normalized = urlunparse((scheme, netloc, path, "", new_query, ""))
    return normalized


def aggregate_citations(citations: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Computes occurrences vs unique normalized URLs.
    """
    total_occurrences = len(citations)
    unique_normalized: Set[str] = set()

    for c in citations:
        url = c.get("url")
        if url:
            norm = normalize_url(url)
            if norm:
                unique_normalized.add(norm)

    return {
        "total_occurrences": total_occurrences,
        "unique_normalized_count": len(unique_normalized),
        "unique_urls": sorted(list(unique_normalized)),
    }
