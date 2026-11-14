#!/usr/bin/env python3
"""Regenerate JSON, prompt-level scores, and the HTML dashboard from source data.

The dashboard is rendered directly from the current database analysis and the
current regression-evaluation result. It never edits a previous report in place.
"""
from __future__ import annotations

import html
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.classification import execute_analysis
from app.database import Base
import app.models  # noqa: F401
from app.export import export_approved_report
from app.ingestion import import_dataset
from app.models import Dataset, Response as DBResponse, ResponseResult
from app.reports import create_initial_report, submit_report_for_review
from app.review import process_review_decision
from app.schemas import ReviewDecisionRequest
from evaluation.run_eval import run_evaluation

RESULTS_DIR = ROOT / "evaluation" / "results"
ENGINE_LABELS = {
    "gemini": "Google Gemini",
    "chatgpt": "OpenAI ChatGPT",
    "aimode": "Google AI Mode",
}
METRIC_LABELS = (
    ("kasparro_mentioned", "Brand mention"),
    ("kasparro_recommended", "Recommendation"),
    ("kasparro_negative", "Negative characterization"),
)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object in {path}")
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Required input file is missing: {path}")
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSON in {path} at line {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise RuntimeError(f"Expected an object in {path} at line {line_number}")
            records.append(item)
    return records


def _require_mapping(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Required report field '{path}' is missing or is not an object")
    return value


def _require_number(value: Any, path: str, *, minimum: Optional[float] = None,
                    maximum: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Required report metric '{path}' is missing or is not numeric")
    number = float(value)
    if not math.isfinite(number):
        raise RuntimeError(f"Required report metric '{path}' must be finite")
    if minimum is not None and number < minimum:
        raise RuntimeError(f"Required report metric '{path}' must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise RuntimeError(f"Required report metric '{path}' must be <= {maximum}")
    return number


def _format_score(value: Any) -> str:
    return f"{_require_number(value, 'score', minimum=0, maximum=100):.1f}"


def _format_rate(value: Any) -> str:
    rate = _require_number(value, "rate", minimum=0, maximum=1)
    return f"{rate * 100:.1f}%"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _load_prompt_lookup() -> Dict[str, str]:
    records = _read_jsonl(ROOT / "data" / "prompts.jsonl")
    lookup: Dict[str, str] = {}
    for record in records:
        prompt_id = record.get("prompt_id")
        text = record.get("text")
        if not isinstance(prompt_id, str) or not isinstance(text, str):
            raise RuntimeError("Prompt records must contain string prompt_id and text fields")
        if prompt_id in lookup:
            raise RuntimeError(f"Duplicate prompt ID in source data: {prompt_id}")
        lookup[prompt_id] = text
    return lookup


def _build_prompt_scores(
    db: Any,
    dataset_id: str,
    analysis_id: str,
    prompt_lookup: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    responses = db.query(DBResponse).filter(DBResponse.dataset_id == dataset_id).all()
    response_by_id = {item.id: item for item in responses}
    result_rows = db.query(ResponseResult).filter(ResponseResult.analysis_id == analysis_id).all()
    grouped: Dict[str, List[Dict[str, Any]]] = {engine: [] for engine in ENGINE_LABELS}

    for result in result_rows:
        response = response_by_id.get(result.response_id)
        if response is None:
            raise RuntimeError(f"Analysis result references missing response row: {result.response_id}")
        try:
            raw_payload = json.loads(response.raw_payload or "{}")
            labels = json.loads(result.labels_json or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not decode stored response/labels for {response.source_response_id}") from exc

        prompt_text = prompt_lookup.get(response.prompt_id)
        if prompt_text is None:
            raise RuntimeError(f"No source prompt found for prompt_id={response.prompt_id}")
        if response.engine not in grouped:
            raise RuntimeError(f"Unexpected engine in analysis results: {response.engine}")

        score = None if result.score is None else _require_number(
            result.score, f"response_score[{response.source_response_id}]", minimum=0, maximum=100
        )
        grouped[response.engine].append({
            "response_id": response.source_response_id,
            "prompt_id": response.prompt_id,
            "prompt_text": prompt_text,
            "engine": response.engine,
            "status": result.status,
            "score": score,
            "mentioned": bool(labels.get("kasparro_mentioned", False)),
            "recommended": bool(labels.get("kasparro_recommended", False)),
            "negative": bool(labels.get("kasparro_negative", False)),
            "is_branded_prompt": "kasparro" in prompt_text.casefold(),
        })

    for engine, items in grouped.items():
        items.sort(key=lambda row: row["prompt_id"])
    return grouped


def _aggregate_prompt_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    scored = [row for row in rows if row["status"] == "success" and row["score"] is not None]
    count = len(scored)
    if not count:
        return {
            "response_count": len(rows),
            "scored_count": 0,
            "mean_score": None,
            "inclusion_rate": None,
            "recommendation_rate": None,
            "negative_rate": None,
        }
    return {
        "response_count": len(rows),
        "scored_count": count,
        "mean_score": round(sum(row["score"] for row in scored) / count, 2),
        "inclusion_rate": sum(row["mentioned"] for row in scored) / count,
        "recommendation_rate": sum(row["recommended"] for row in scored) / count,
        "negative_rate": sum(row["negative"] for row in scored) / count,
    }


def _build_scope_summaries(prompt_scores: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    all_rows = [row for rows in prompt_scores.values() for row in rows]
    return {
        "all": _aggregate_prompt_rows(all_rows),
        "branded_prompts": _aggregate_prompt_rows(
            row for row in all_rows if row["is_branded_prompt"]
        ),
        "unbranded_prompts": _aggregate_prompt_rows(
            row for row in all_rows if not row["is_branded_prompt"]
        ),
    }


def _render_metric_card(label: str, value: str, detail: str = "") -> str:
    return (
        '<article class="metric-card">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f'<div class="metric-detail">{html.escape(detail)}</div>'
        '</article>'
    )


def _render_engine_rows(engine_aggregates: Dict[str, Any],
                        prompt_scores: Dict[str, List[Dict[str, Any]]]) -> str:
    rows = []
    for engine, label in ENGINE_LABELS.items():
        metrics = _require_mapping(engine_aggregates.get(engine), f"engine_aggregates.{engine}")
        distribution = _require_mapping(metrics.get("distribution"), f"engine_aggregates.{engine}.distribution")
        row_count = len(prompt_scores.get(engine, []))
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{html.escape(label)}</th>"
            f"<td>{row_count}</td>"
            f"<td>{_format_score(metrics.get('mean_score'))}</td>"
            f"<td>{_format_rate(distribution.get('inclusion_rate'))}</td>"
            f"<td>{_format_rate(distribution.get('recommendation_rate'))}</td>"
            f"<td>{_format_rate(distribution.get('negative_rate'))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_scope_rows(scope_summaries: Dict[str, Dict[str, Any]]) -> str:
    rows = []
    labels = (
        ("all", "All prompts"),
        ("branded_prompts", "Prompts containing the brand"),
        ("unbranded_prompts", "Prompts without the brand"),
    )
    for key, label in labels:
        stats = scope_summaries[key]
        if stats["scored_count"] == 0:
            values = ("N/A", "N/A", "N/A", "N/A", "0")
        else:
            values = (
                _format_score(stats["mean_score"]),
                _format_rate(stats["inclusion_rate"]),
                _format_rate(stats["recommendation_rate"]),
                _format_rate(stats["negative_rate"]),
                str(stats["scored_count"]),
            )
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{html.escape(label)}</th>"
            + "".join(f"<td>{html.escape(value)}</td>" for value in values)
            + "</tr>"
        )
    return "\n".join(rows)


def _render_evaluation(eval_result: Dict[str, Any]) -> str:
    counts = _require_mapping(eval_result.get("counts"), "evaluation.counts")
    baseline = _require_mapping(eval_result.get("baseline_metrics"), "evaluation.baseline_metrics")
    proposed = _require_mapping(eval_result.get("proposed_metrics"), "evaluation.proposed_metrics")
    total = int(_require_number(counts.get("total_cases"), "evaluation.counts.total_cases", minimum=0))
    evaluated = int(_require_number(counts.get("evaluated_cases"), "evaluation.counts.evaluated_cases", minimum=0))
    failed = int(_require_number(counts.get("failed_cases"), "evaluation.counts.failed_cases", minimum=0))
    if evaluated + failed != total:
        raise RuntimeError("Evaluation case counts are inconsistent: evaluated + failed must equal total")

    baseline_rate = _require_number(baseline.get("agreement_rate"), "baseline.agreement_rate", minimum=0, maximum=1)
    proposed_rate = _require_number(proposed.get("agreement_rate"), "proposed.agreement_rate", minimum=0, maximum=1)
    baseline_labels = _require_mapping(baseline.get("per_label"), "baseline.per_label")
    proposed_labels = _require_mapping(proposed.get("per_label"), "proposed.per_label")

    rows = []
    for key, label in METRIC_LABELS:
        base = _require_mapping(baseline_labels.get(key), f"baseline.{key}")
        current = _require_mapping(proposed_labels.get(key), f"proposed.{key}")
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{html.escape(label)}</th>"
            f"<td>{_format_rate(base.get('precision')) if base.get('precision') is not None else 'N/A'}</td>"
            f"<td>{_format_rate(current.get('precision')) if current.get('precision') is not None else 'N/A'}</td>"
            f"<td>{_format_rate(base.get('recall')) if base.get('recall') is not None else 'N/A'}</td>"
            f"<td>{_format_rate(current.get('recall')) if current.get('recall') is not None else 'N/A'}</td>"
            f"<td>{_format_rate(base.get('f1')) if base.get('f1') is not None else 'N/A'}</td>"
            f"<td>{_format_rate(current.get('f1')) if current.get('f1') is not None else 'N/A'}</td>"
            "</tr>"
        )

    delta = (proposed_rate - baseline_rate) * 100
    return f"""
    <section class="panel" id="evaluation">
      <div class="section-heading">
        <div><p class="eyebrow">Classifier evaluation</p><h2>Regression benchmark</h2></div>
        <span class="tag">Replay · {total} cases</span>
      </div>
      <p class="muted">This is the checked-in regression set, not an independently annotated held-out benchmark. Provider execution is reported separately.</p>
      <div class="evaluation-summary">
        <div><span class="metric-label">Baseline exact-match agreement</span><strong>{baseline_rate * 100:.1f}%</strong></div>
        <div><span class="metric-label">Replay exact-match agreement</span><strong>{proposed_rate * 100:.1f}%</strong></div>
        <div><span class="metric-label">Agreement delta</span><strong>{delta:+.1f} pp</strong></div>
        <div><span class="metric-label">Evaluated / failed</span><strong>{evaluated} / {failed}</strong></div>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th>Label</th><th>Baseline P</th><th>Replay P</th><th>Baseline R</th><th>Replay R</th><th>Baseline F1</th><th>Replay F1</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table></div>
      <p class="footnote">Interpretation is limited by the sample size and composition shown above. A high regression score is not proof of broad real-world generalization.</p>
    </section>
    """


def render_dashboard_html(
    final_report: Dict[str, Any],
    eval_result: Dict[str, Any],
    prompt_scores: Dict[str, List[Dict[str, Any]]],
) -> str:
    """Render a fresh dashboard from validated report and evaluation structures."""
    counts = _require_mapping(final_report.get("counts"), "counts")
    scoring = _require_mapping(final_report.get("scoring"), "scoring")
    provenance = _require_mapping(final_report.get("provenance"), "provenance")
    distribution = _require_mapping(scoring.get("overall_distribution"), "scoring.overall_distribution")
    engine_aggregates = _require_mapping(scoring.get("engine_aggregates"), "scoring.engine_aggregates")

    overall_score = _require_number(scoring.get("overall_mean_score"), "scoring.overall_mean_score", minimum=0, maximum=100)
    overall_inclusion = _format_rate(distribution.get("inclusion_rate"))
    overall_recommendation = _format_rate(distribution.get("recommendation_rate"))
    overall_negative = _format_rate(distribution.get("negative_rate"))
    eligible = int(_require_number(counts.get("eligible_responses"), "counts.eligible_responses", minimum=0))
    successful = int(_require_number(counts.get("successful_responses"), "counts.successful_responses", minimum=0))
    failed = int(_require_number(counts.get("failed_responses"), "counts.failed_responses", minimum=0))
    skipped = int(_require_number(counts.get("skipped_responses"), "counts.skipped_responses", minimum=0))
    if successful + failed + skipped != eligible:
        raise RuntimeError("Analysis response counts are inconsistent: successful + failed + skipped must equal eligible")

    total_prompts = int(_require_number(counts.get("supplied_prompts"), "counts.supplied_prompts", minimum=0))
    total_responses = int(_require_number(counts.get("supplied_responses"), "counts.supplied_responses", minimum=0))
    total_citations = int(_require_number(counts.get("supplied_citations"), "counts.supplied_citations", minimum=0))
    scope_summaries = _build_scope_summaries(prompt_scores)

    cards = "".join([
        _render_metric_card("Overall visibility score", f"{overall_score:.2f} / 100", "Scoring v1 · replay analysis"),
        _render_metric_card("Brand inclusion", overall_inclusion, f"{successful} successfully classified responses"),
        _render_metric_card("Recommendation rate", overall_recommendation, "Among successfully classified responses"),
        _render_metric_card("Negative characterization", overall_negative, "Among successfully classified responses"),
    ])
    stats = "".join([
        _render_metric_card("Prompts", str(total_prompts), "Source dataset"),
        _render_metric_card("AI responses", str(total_responses), "Source dataset"),
        _render_metric_card("Citation entries", f"{total_citations:,}", "Source dataset"),
        _render_metric_card("Failed / skipped", f"{failed} / {skipped}", f"{eligible} eligible responses"),
    ])

    diagnostics = final_report.get("diagnostics") or []
    diagnostic_html = []
    for diagnostic in diagnostics:
        title = html.escape(str(diagnostic.get("title") or "Evidence-backed finding"))
        pattern = html.escape(str(diagnostic.get("observed_pattern") or ""))
        comparison = html.escape(str(diagnostic.get("comparison") or ""))
        evidence_html = []
        for item in diagnostic.get("evidence") or []:
            excerpt = html.escape(str(item.get("excerpt") or ""))
            response_id = html.escape(str(item.get("response_id") or "unknown"))
            engine_name = html.escape(str(ENGINE_LABELS.get(item.get("engine"), item.get("engine") or "Unknown engine")))
            start = item.get("start_offset")
            end = item.get("end_offset")
            location = html.escape(str(item.get("location") or "answer_text"))
            offset_text = f" · chars {start}–{end}" if isinstance(start, int) and isinstance(end, int) else ""
            evidence_html.append(
                f'<blockquote><p>“{excerpt}”</p><small>{engine_name} · response {response_id} · {location}{offset_text}</small></blockquote>'
            )
        diagnostic_html.append(
            f'<article class="diagnostic"><h3>{title}</h3><p>{pattern}</p><p class="muted">{comparison}</p>'
            + "".join(evidence_html)
            + "</article>"
        )
    if not diagnostic_html:
        diagnostic_html.append('<p class="muted">No evidence-backed diagnostics were generated for this analysis.</p>')

    remedies_html = []
    for remedy in final_report.get("remedies") or []:
        title = html.escape(str(remedy.get("title") or remedy.get("action") or "Recommended action"))
        description = html.escape(str(remedy.get("description") or remedy.get("rationale") or ""))
        validation = html.escape(str(remedy.get("validation_target") or remedy.get("success_metric") or ""))
        remedies_html.append(
            f'<article class="remedy"><h3>{title}</h3><p>{description}</p>'
            + (f'<p class="muted"><strong>Validation:</strong> {validation}</p>' if validation else "")
            + "</article>"
        )
    if not remedies_html:
        remedies_html.append('<p class="muted">No remedies were generated for this analysis.</p>')

    generated_at = html.escape(str(final_report.get("generated_at") or ""))
    snapshot_date = html.escape(str(provenance.get("historical_capture_date") or "Not recorded"))
    location = html.escape(str(provenance.get("location") or "Not recorded"))
    language = html.escape(str(provenance.get("language") or "Not recorded"))
    dataset_name = html.escape(str(provenance.get("dataset_name") or "Dataset"))
    source_hash = html.escape(str(provenance.get("source_hash") or "Not recorded"))
    run_id = html.escape(str(provenance.get("run_id") or "Not recorded"))
    dataset_id = html.escape(str(provenance.get("dataset_id") or "Not recorded"))
    execution_mode = html.escape(str(scoring.get("execution_mode") or "unknown"))
    engine_rows = _render_engine_rows(engine_aggregates, prompt_scores)
    scope_rows = _render_scope_rows(scope_summaries)
    evaluation_html = _render_evaluation(eval_result)

    html_document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Evidence-backed AI visibility analysis generated from the validated dataset and analysis run.">
<title>Kasparro · AI Visibility Analysis</title>
<style>
:root{{--bg:#f4f6fa;--surface:#fff;--ink:#152238;--muted:#66758b;--line:#e3e8f0;--blue:#3457d5;--teal:#16856f;--amber:#a86a13;--red:#b54747;--shadow:0 12px 34px rgba(20,35,60,.07)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}}
header{{background:linear-gradient(125deg,#172b52,#253d75);color:white;padding:48px max(24px,calc((100vw - 1180px)/2)) 42px}}
.eyebrow{{font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;color:#8299e8;margin:0 0 8px}}
h1{{font-size:clamp(30px,5vw,48px);line-height:1.12;margin:0 0 12px;letter-spacing:-.035em}}header p{{color:#d2dcf0;max-width:760px;margin:0}}
.meta{{display:flex;flex-wrap:wrap;gap:9px;margin-top:22px}}.meta span,.tag{{border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08);border-radius:999px;padding:5px 11px;font-size:12px}}
main{{max-width:1180px;margin:28px auto 60px;padding:0 22px}}.section{{margin:28px 0}}.section-heading{{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:14px}}h2{{font-size:23px;line-height:1.2;margin:0;letter-spacing:-.025em}}h3{{font-size:17px;margin:0 0 8px}}
.panel{{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:24px;margin:22px 0;box-shadow:var(--shadow)}}.metric-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}}
.metric-card{{background:var(--surface);border:1px solid var(--line);border-radius:15px;padding:18px;box-shadow:var(--shadow);min-width:0}}
.metric-label{{display:block;color:var(--muted);font-size:12px;font-weight:700}}.metric-value{{display:block;font-size:27px;font-weight:800;letter-spacing:-.04em;margin:7px 0 2px}}.metric-detail,.muted,.footnote{{font-size:12px;color:var(--muted)}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:12px 13px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}}thead th{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);background:#f8f9fc}}tbody th{{font-weight:700}}
.evaluation-summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}}.evaluation-summary>div{{background:#f7f9fd;border:1px solid var(--line);padding:14px;border-radius:12px}}.evaluation-summary strong{{display:block;font-size:23px;margin-top:4px}}
.diagnostic,.remedy{{border-top:1px solid var(--line);padding:18px 0}}.diagnostic:first-child,.remedy:first-child{{border-top:0;padding-top:0}}
blockquote{{margin:12px 0;padding:12px 15px;background:#f7f9fc;border-left:3px solid var(--blue);border-radius:0 10px 10px 0}}blockquote p{{margin:0 0 6px}}blockquote small{{font-size:11px;color:var(--muted);overflow-wrap:anywhere}}
.provenance{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.provenance div{{background:#f8f9fc;border:1px solid var(--line);border-radius:10px;padding:12px;overflow-wrap:anywhere}}.provenance small{{display:block;color:var(--muted)}}
.notice{{border:1px solid #f0dcae;background:#fff9ea;color:#6e4b16;padding:14px 16px;border-radius:12px;font-size:13px}}
footer{{text-align:center;color:var(--muted);font-size:12px;padding:30px 0 12px}}
@media(max-width:850px){{.metric-grid,.evaluation-summary{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:560px){{.metric-grid,.evaluation-summary,.provenance{{grid-template-columns:1fr}}header{{padding-top:34px}}.panel{{padding:17px}}}}
</style>
</head>
<body>
<header>
  <p class="eyebrow">Historical snapshot · Evidence-backed analysis</p>
  <h1>Kasparro AI Visibility Analysis</h1>
  <p>Analysis generated from the supplied prompt/response dataset, validated classification outputs and source-traceable diagnostics.</p>
  <div class="meta"><span>Snapshot: {snapshot_date}</span><span>Location: {location} ({language})</span><span>Execution: {execution_mode}</span><span>Generated: {generated_at}</span></div>
</header>
<main>
  <section class="section">
    <div class="section-heading"><div><p class="eyebrow">Dataset coverage</p><h2>Source dataset and processing status</h2></div></div>
    <div class="metric-grid">{stats}</div>
  </section>
  <section class="section">
    <div class="section-heading"><div><p class="eyebrow">Visibility metrics</p><h2>Overall results</h2></div></div>
    <div class="metric-grid">{cards}</div>
  </section>
  <section class="panel">
    <div class="section-heading"><div><p class="eyebrow">Engine comparison</p><h2>Visibility by answer engine</h2></div><span class="tag" style="color:var(--muted);border-color:var(--line);background:#f8f9fc">Successful scored responses</span></div>
    <div class="table-wrap"><table><thead><tr><th>Engine</th><th>Responses</th><th>Mean score</th><th>Inclusion</th><th>Recommendation</th><th>Negative</th></tr></thead><tbody>{engine_rows}</tbody></table></div>
  </section>
  <section class="panel">
    <div class="section-heading"><div><p class="eyebrow">Prompt cohorts</p><h2>Brand-led vs category discovery prompts</h2></div></div>
    <p class="muted">Cohorts are derived from whether the source prompt text contains the brand name; no fixed prompt-number range is assumed.</p>
    <div class="table-wrap"><table><thead><tr><th>Cohort</th><th>Mean score</th><th>Inclusion</th><th>Recommendation</th><th>Negative</th><th>Scored responses</th></tr></thead><tbody>{scope_rows}</tbody></table></div>
  </section>
  {evaluation_html}
  <section class="panel">
    <div class="section-heading"><div><p class="eyebrow">Source-grounded findings</p><h2>Evidence-backed diagnostics</h2></div></div>
    {''.join(diagnostic_html)}
  </section>
  <section class="panel">
    <div class="section-heading"><div><p class="eyebrow">Action plan</p><h2>Prioritized remedies</h2></div></div>
    {''.join(remedies_html)}
  </section>
  <section class="panel">
    <div class="section-heading"><div><p class="eyebrow">Data provenance</p><h2>Run metadata</h2></div></div>
    <div class="provenance">
      <div><small>Dataset</small>{dataset_name}</div>
      <div><small>Run ID</small>{run_id}</div>
      <div><small>Dataset ID</small>{dataset_id}</div>
      <div><small>Source hash</small>{source_hash}</div>
      <div><small>Scoring version</small>{html.escape(str(scoring.get('scoring_version') or 'Not recorded'))}</div>
      <div><small>Classifier version</small>{html.escape(str(scoring.get('classifier_version') or 'Not recorded'))}</div>
    </div>
  </section>
  <div class="notice">Limitations: this report describes one historical capture, not current live model rankings. The classifier evaluation shown above uses the checked-in regression set; it is not an independent real-world accuracy estimate. A live provider evaluation must be reported separately from replay.</div>
  <footer>Generated from validated source data and the current analysis run · {generated_at}</footer>
</main>
</body>
</html>
"""
    # Fail closed if stale test-count labels or the old fallback metric leak into output.
    forbidden = ("76 Tests Collected", "21/21 Tests Pass", "37.57")
    leaked = [value for value in forbidden if value in html_document]
    if leaked:
        raise RuntimeError(f"Stale dashboard content detected: {leaked}")
    return html_document


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt_lookup = _load_prompt_lookup()
    run_metadata = _read_json(ROOT / "data" / "run.json")

    regression_eval = run_evaluation(
        execution_mode="replay",
        output_dir=str(RESULTS_DIR),
        split="regression",
    )
    held_out_eval = run_evaluation(
        execution_mode="replay",
        output_dir=str(RESULTS_DIR),
        split="held_out",
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        imported = import_dataset(
            db,
            dataset_name="kasparro-historical-snapshot",
            source_directory=str(ROOT / "data"),
        )
        analysis = execute_analysis(db, dataset_id=imported.dataset_id, execution_mode="replay")
        if analysis.status != "completed":
            raise RuntimeError(f"Analysis did not complete successfully: status={analysis.status}")

        report = create_initial_report(db, dataset_id=imported.dataset_id, analysis_id=analysis.id)
        submitted = submit_report_for_review(db, report.id)
        process_review_decision(
            db,
            report.id,
            ReviewDecisionRequest(
                version_id=submitted.id,
                decision="approve",
                comment="Generated from the current analysis and validated source evidence.",
            ),
        )
        exported = export_approved_report(db, report.id)
        dataset_row = db.query(Dataset).filter(Dataset.id == imported.dataset_id).first()
        if dataset_row is None:
            raise RuntimeError("Imported dataset row could not be reloaded")

        analysis_config = _require_mapping(
            json.loads(analysis.configuration_json or "{}"),
            "analysis.configuration",
        )
        overall = _require_mapping(analysis_config.get("overall"), "analysis.overall")
        prompt_scores = _build_prompt_scores(
            db,
            imported.dataset_id,
            analysis.id,
            prompt_lookup,
        )
        generated_at = datetime.now(timezone.utc).isoformat()
        final_report = {
            "title": "Kasparro AI Visibility Analysis & Human Review",
            "pack_version": "1.0.0",
            "generated_at": generated_at,
            "provenance": {
                "run_id": analysis.id,
                "dataset_id": imported.dataset_id,
                "dataset_name": dataset_row.name,
                "source_hash": dataset_row.source_hash,
                "historical_capture_date": run_metadata.get("historical_capture_date"),
                "location": run_metadata.get("location"),
                "language": run_metadata.get("language"),
                "provider": run_metadata.get("capture_provider"),
                "source_run_id": run_metadata.get("run_id"),
            },
            "counts": {
                "supplied_prompts": imported.imported_prompts,
                "supplied_responses": imported.imported_responses,
                "supplied_citations": imported.imported_citations,
                "eligible_responses": overall.get("total_eligible"),
                "successful_responses": overall.get("total_successful"),
                "failed_responses": overall.get("total_failed"),
                "skipped_responses": overall.get("total_skipped"),
            },
            "scoring": {
                "scoring_version": analysis.scoring_version,
                "classifier_version": analysis.classifier_version,
                "execution_mode": analysis.execution_mode,
                "overall_mean_score": overall.get("mean_score"),
                "overall_distribution": overall.get("distribution"),
                "engine_aggregates": analysis_config.get("engine_aggregates"),
                "category_aggregates": analysis_config.get("category_aggregates"),
            },
            "evaluation": {
                "regression": {
                    "counts": regression_eval.get("counts"),
                    "baseline_metrics": regression_eval.get("baseline_metrics"),
                    "proposed_metrics": regression_eval.get("proposed_metrics"),
                    "execution_metadata": regression_eval.get("execution_metadata"),
                },
                "held_out": {
                    "counts": held_out_eval.get("counts"),
                    "annotation_note": held_out_eval.get("counts", {}).get("annotation_note"),
                },
            },
            "diagnostics": exported["content"].get("diagnostics", []),
            "remedies": exported["content"].get("remedies", []),
            "evidence_validation": exported["content"].get("evidence_validation", {}),
        }

        _write_json(RESULTS_DIR / "prompt_scores.json", prompt_scores)
        _write_json(RESULTS_DIR / "final_report.json", final_report)
        dashboard = render_dashboard_html(final_report, regression_eval, prompt_scores)
        _write_text(RESULTS_DIR / "report.html", dashboard)

        print("Artifact regeneration completed.")
        print(f"  Dataset: {imported.imported_prompts} prompts, {imported.imported_responses} responses, {imported.imported_citations} citations")
        print(f"  Analysis: {analysis.status} ({overall.get('total_successful')} successful, {overall.get('total_failed')} failed, {overall.get('total_skipped')} skipped)")
        print(f"  Regression evaluation: {regression_eval['counts']['evaluated_cases']}/{regression_eval['counts']['total_cases']} evaluated")
        print(f"  Held-out candidate evaluation: {held_out_eval['counts']['evaluated_cases']}/{held_out_eval['counts']['total_cases']} evaluated")
        print("  Generated: final_report.json, prompt_scores.json, report.html")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
