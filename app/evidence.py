import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Tuple, Optional, List, Dict, Set, Any


def validate_evidence(excerpt: str, source_text: str) -> Tuple[bool, Optional[str]]:
    """
    Validates that the given evidence excerpt exists verbatim in the source text.
    Rejects fabricated or hallucinated evidence.
    """
    if not excerpt or not excerpt.strip():
        return False, "Evidence excerpt is empty"
    if not source_text:
        return False, "Source text is empty"

    if excerpt.strip() in source_text:
        return True, None

    # Try normalized whitespace match
    norm_excerpt = re.sub(r"\s+", " ", excerpt.strip())
    norm_source = re.sub(r"\s+", " ", source_text)
    if norm_excerpt in norm_source:
        return True, None

    return False, f"Excerpt '{excerpt[:50]}...' not found verbatim in source text."


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
