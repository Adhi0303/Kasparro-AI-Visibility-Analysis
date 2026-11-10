import html
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import Tuple, Optional, List, Dict, Set, Any


SUPPORTED_EVIDENCE_LOCATIONS: Set[str] = {"answer_text"}


def resolve_evidence_source(
    location: Any,
    sources: Dict[str, str],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Resolves an evidence location to an authorized source text buffer.
    Rejects unsupported, missing, or blank locations without silently rewriting them.
    """
    if not isinstance(location, str) or not location.strip():
        return False, None, f"Unsupported evidence location: {location!r}"
    if location not in SUPPORTED_EVIDENCE_LOCATIONS:
        return False, None, f"Unsupported evidence location: '{location}'"
    if location not in sources or not isinstance(sources[location], str) or not sources[location]:
        return False, None, f"Source text is empty for location '{location}'"
    return True, sources[location], None


def find_evidence_match(
    excerpt: str,
    source_text: str,
    location: str = "answer_text",
) -> Dict[str, Any]:
    """
    Locates an evidence excerpt inside source_text for an authorized location and
    returns validation metadata with zero-based [start_offset, end_offset) character spans.
    For whitespace-normalized matches, maps spans back to the original source slice.
    """
    if not isinstance(location, str) or location not in SUPPORTED_EVIDENCE_LOCATIONS:
        return {
            "valid": False,
            "start_offset": None,
            "end_offset": None,
            "match_type": None,
            "canonical_excerpt": None,
            "submitted_excerpt": excerpt if isinstance(excerpt, str) else "",
            "rejection_reason": f"Unsupported evidence location: {location!r}",
        }

    if not isinstance(excerpt, str) or not excerpt.strip():
        return {
            "valid": False,
            "start_offset": None,
            "end_offset": None,
            "match_type": None,
            "canonical_excerpt": None,
            "submitted_excerpt": excerpt if isinstance(excerpt, str) else "",
            "rejection_reason": "Evidence excerpt is empty",
        }
    if not isinstance(source_text, str) or not source_text:
        return {
            "valid": False,
            "start_offset": None,
            "end_offset": None,
            "match_type": None,
            "canonical_excerpt": None,
            "submitted_excerpt": excerpt,
            "rejection_reason": "Source text is empty",
        }

    # 1. Exact raw substring match (ensures source_text[start:end] == excerpt)
    exact_idx = source_text.find(excerpt)
    if exact_idx != -1:
        end_idx = exact_idx + len(excerpt)
        return {
            "valid": True,
            "start_offset": exact_idx,
            "end_offset": end_idx,
            "match_type": "exact",
            "canonical_excerpt": source_text[exact_idx:end_idx],
            "submitted_excerpt": excerpt,
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
            "canonical_excerpt": source_text[orig_start:orig_end],
            "submitted_excerpt": excerpt,
            "rejection_reason": None,
        }

    return {
        "valid": False,
        "start_offset": None,
        "end_offset": None,
        "match_type": None,
        "canonical_excerpt": None,
        "submitted_excerpt": excerpt,
        "rejection_reason": f"Excerpt '{excerpt.strip()[:50]}...' not found verbatim in source text.",
    }


def validate_evidence(
    excerpt: str,
    source_text: str,
    location: str = "answer_text",
) -> Tuple[bool, Optional[str]]:
    """
    Validates that the given evidence excerpt exists verbatim in the authorized source text.
    Rejects fabricated, empty, or unsupported-location evidence.
    """
    result = find_evidence_match(excerpt, source_text, location=location)
    if result["valid"]:
        return True, None
    return False, result["rejection_reason"]


def validate_report_evidence(
    diagnostics: List[Dict[str, Any]],
    source_lookup: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validates all evidence items referenced by downstream diagnostics against source_lookup.
    - Verifies response_id exists cleanly without crashing on missing sources
    - Verifies declared evidence location is supported
    - Verifies offsets (if present) and canonical source slice alignment
    - Strips rejected evidence from rendered diagnostic evidence lists and records rejections
    """
    validated_diagnostics: List[Dict[str, Any]] = []
    accepted_audit: List[Dict[str, Any]] = []
    rejected_audit: List[Dict[str, Any]] = []

    for diag in diagnostics or []:
        diag_copy = dict(diag)
        valid_items: List[Dict[str, Any]] = []

        for ev in diag.get("evidence", []) or []:
            if not isinstance(ev, dict):
                rejected_audit.append({
                    "diagnostic_title": diag.get("title"),
                    "excerpt": "",
                    "validation_status": "rejected",
                    "rejection_reason": f"Malformed report evidence item: {type(ev).__name__}",
                })
                continue

            rid = ev.get("response_id")
            raw_loc = ev["location"] if "location" in ev else "answer_text"
            excerpt = ev.get("excerpt")

            if not isinstance(rid, str) or rid not in source_lookup:
                rejected_audit.append({
                    "diagnostic_title": diag.get("title"),
                    "response_id": rid,
                    "location": raw_loc,
                    "excerpt": excerpt if isinstance(excerpt, str) else "",
                    "validation_status": "rejected",
                    "rejection_reason": f"Source response '{rid}' not found in dataset",
                })
                continue

            sources = source_lookup[rid]
            loc_ok, source_text, loc_err = resolve_evidence_source(raw_loc, sources)
            if not loc_ok or source_text is None:
                rejected_audit.append({
                    "diagnostic_title": diag.get("title"),
                    "response_id": rid,
                    "location": raw_loc,
                    "excerpt": excerpt if isinstance(excerpt, str) else "",
                    "validation_status": "rejected",
                    "rejection_reason": loc_err or "Unsupported evidence location",
                })
                continue

            if not isinstance(excerpt, str) or not excerpt.strip():
                rejected_audit.append({
                    "diagnostic_title": diag.get("title"),
                    "response_id": rid,
                    "location": raw_loc,
                    "excerpt": "",
                    "validation_status": "rejected",
                    "rejection_reason": "Evidence excerpt is empty",
                })
                continue

            start_off = ev.get("start_offset")
            end_off = ev.get("end_offset")
            ev_valid = False
            canonical_excerpt = None
            match_type = ev.get("match_type")
            reject_reason = None

            if start_off is not None or end_off is not None:
                if (
                    isinstance(start_off, int)
                    and not isinstance(start_off, bool)
                    and isinstance(end_off, int)
                    and not isinstance(end_off, bool)
                    and 0 <= start_off < end_off <= len(source_text)
                ):
                    actual_slice = source_text[start_off:end_off]
                    norm_actual = re.sub(r"\s+", " ", actual_slice.strip())
                    norm_excerpt = re.sub(r"\s+", " ", excerpt.strip())
                    if actual_slice == excerpt:
                        ev_valid = True
                        canonical_excerpt = actual_slice
                        match_type = match_type or "exact"
                    elif norm_actual == norm_excerpt:
                        ev_valid = True
                        canonical_excerpt = actual_slice
                        match_type = "normalized_whitespace"
                    else:
                        reject_reason = "Source slice at declared offsets does not match excerpt"
                else:
                    reject_reason = f"Invalid source offsets [{start_off}, {end_off}) for response '{rid}'"
            else:
                match = find_evidence_match(excerpt, source_text, location=raw_loc)
                if match["valid"]:
                    ev_valid = True
                    start_off = match["start_offset"]
                    end_off = match["end_offset"]
                    canonical_excerpt = match["canonical_excerpt"]
                    match_type = match["match_type"]
                else:
                    reject_reason = match["rejection_reason"]

            if ev_valid and canonical_excerpt is not None:
                clean_ev = dict(ev)
                clean_ev["excerpt"] = canonical_excerpt
                clean_ev["location"] = raw_loc
                clean_ev["start_offset"] = start_off
                clean_ev["end_offset"] = end_off
                clean_ev["match_type"] = match_type
                clean_ev["validation_status"] = "valid"
                if canonical_excerpt != excerpt:
                    clean_ev["submitted_excerpt"] = excerpt
                valid_items.append(clean_ev)
                accepted_audit.append({
                    "diagnostic_title": diag.get("title"),
                    "response_id": rid,
                    "location": raw_loc,
                    "start_offset": start_off,
                    "end_offset": end_off,
                    "validation_status": "valid",
                })
            else:
                rejected_audit.append({
                    "diagnostic_title": diag.get("title"),
                    "response_id": rid,
                    "location": raw_loc,
                    "excerpt": excerpt,
                    "validation_status": "rejected",
                    "rejection_reason": reject_reason or "Failed report evidence validation",
                })

        diag_copy["evidence"] = valid_items
        validated_diagnostics.append(diag_copy)

    audit_summary = {
        "accepted_count": len(accepted_audit),
        "rejected_count": len(rejected_audit),
        "accepted": accepted_audit,
        "rejected": rejected_audit,
    }
    return validated_diagnostics, audit_summary


def render_report_markdown(
    report_payload: Dict[str, Any],
    source_lookup: Optional[Dict[str, Dict[str, str]]] = None,
) -> str:
    """
    Renders a validated Markdown summary of an exported/approved report.
    Ensures only verified canonical evidence is rendered.
    """
    content = report_payload.get("content", report_payload)
    diagnostics = content.get("diagnostics", [])
    if source_lookup is not None:
        diagnostics, _ = validate_report_evidence(diagnostics, source_lookup)

    lines: List[str] = [
        f"# {content.get('title', 'Kasparro AI Visibility Report')}",
        "",
        f"**Dataset:** {content.get('dataset_name', 'N/A')}  ",
        f"**Source Hash:** `{content.get('source_hash', 'N/A')}`  ",
        "",
        "## Diagnostics",
        "",
    ]

    for idx, diag in enumerate(diagnostics, 1):
        lines.append(f"### {idx}. {diag.get('title', 'Untitled Finding')}")
        lines.append("")
        lines.append(f"- **Observed Pattern:** {diag.get('observed_pattern', '')}")
        if diag.get("comparison"):
            lines.append(f"- **Comparison:** {diag['comparison']}")
        lines.append("")
        evidence_items = diag.get("evidence", [])
        if evidence_items:
            lines.append("**Verified Evidence:**")
            for ev in evidence_items:
                rid = ev.get("response_id", "unknown")
                loc = ev.get("location", "answer_text")
                span = f"[{ev.get('start_offset')}:{ev.get('end_offset')}]" if ev.get("start_offset") is not None else ""
                lines.append(f"> {ev.get('excerpt', '')}")
                lines.append(f"> *(Response `{rid}`, location `{loc}` {span})*")
                lines.append("")
        else:
            lines.append("*No verified evidence items available for this finding.*")
            lines.append("")

    return "\n".join(lines)


def render_report_html(
    report_payload: Dict[str, Any],
    source_lookup: Optional[Dict[str, Dict[str, str]]] = None,
) -> str:
    """
    Renders an HTML report view using validated evidence and strict HTML escaping
    for all dynamic fields.
    """
    content = report_payload.get("content", report_payload)
    diagnostics = content.get("diagnostics", [])
    if source_lookup is not None:
        diagnostics, _ = validate_report_evidence(diagnostics, source_lookup)

    esc = lambda v: html.escape(str(v or ""), quote=True)
    parts: List[str] = [
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        f"<title>{esc(content.get('title', 'Kasparro Report'))}</title>",
        "</head><body>",
        f"<h1>{esc(content.get('title', 'Kasparro Report'))}</h1>",
        f"<p><strong>Dataset:</strong> {esc(content.get('dataset_name', 'N/A'))}</p>",
        "<section id=\"diagnostics\">",
    ]

    for diag in diagnostics:
        parts.append("<article class=\"diagnostic-card\">")
        parts.append(f"<h2>{esc(diag.get('title', ''))}</h2>")
        parts.append(f"<p>{esc(diag.get('observed_pattern', ''))}</p>")
        for ev in diag.get("evidence", []):
            parts.append("<blockquote class=\"evidence-quote\">")
            parts.append(f"<p>{esc(ev.get('excerpt', ''))}</p>")
            parts.append(
                f"<footer>Response: <code>{esc(ev.get('response_id', ''))}</code> | "
                f"Location: <span>{esc(ev.get('location', ''))}</span> | "
                f"Span: <span>{esc(ev.get('start_offset'))}:{esc(ev.get('end_offset'))}</span></footer>"
            )
            parts.append("</blockquote>")
        parts.append("</article>")

    parts.append("</section></body></html>")
    return "\n".join(parts)


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
