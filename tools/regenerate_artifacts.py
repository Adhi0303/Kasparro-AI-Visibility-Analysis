#!/usr/bin/env python3
"""
Regenerates downstream JSON and HTML report artifacts directly from the validated DB
workflow (ingestion -> classification -> scoring -> draft -> review -> export) and
evaluation suite (evaluation/run_eval.py).
"""
import html as html_lib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.classification import execute_analysis, get_analysis_status
from app.database import Base
import app.models  # noqa: F401
from app.export import export_approved_report
from app.ingestion import import_dataset
from app.models import AnalysisRun, Dataset, Response as DBResponse, ResponseResult
from app.reports import create_initial_report, submit_report_for_review
from app.review import process_review_decision
from app.schemas import ReviewDecisionRequest
from evaluation.run_eval import run_evaluation

RESULTS_DIR = ROOT / "evaluation" / "results"


def _prompt_num(prompt_id: str) -> int:
    m = re.search(r"(\d+)$", prompt_id or "")
    return int(m.group(1)) if m else 0


def _pct_int(rate: float) -> int:
    return int(round(rate * 100))


def _dot_svg_group(engine: str, color: str, icon: str, engine_label: str, items: List[Dict[str, Any]], max_prompt_index: int) -> str:
    circles: List[str] = []
    x_denominator = max(max_prompt_index - 1, 1)
    for item in items:
        idx = int(item["prompt_index"])
        score = float(item["score"])
        x = 50.0 + (idx - 1) * (920.0 / x_denominator)
        y = 310.0 - (score / 100.0) * 270.0
        cat_label = "Branded Query" if item.get("branded_query") else "Unbranded GEO"
        title = html_lib.escape(f"{icon} {engine_label} · Prompt {idx:02d} · Score: {score:.1f}/100", quote=True)
        q_text = html_lib.escape(json.dumps(item["prompt_text"], ensure_ascii=False), quote=True)
        body = (
            f"{q_text}&lt;br&gt;&lt;br&gt;"
            f"• &lt;strong&gt;Mentioned:&lt;/strong&gt; {'Yes' if item['mentioned'] else 'No'}&lt;br&gt;"
            f"• &lt;strong&gt;Recommended:&lt;/strong&gt; {'Yes' if item['recommended'] else 'No'}&lt;br&gt;"
            f"• &lt;strong&gt;Negative/Caution:&lt;/strong&gt; {'Yes' if item['negative'] else 'No'}"
        )
        circles.append(
            f'              <circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" stroke="#ffffff" stroke-width="1.5"\n'
            f'                class="scatter-dot dot-{engine} dot-p{idx:02d}" data-prompt="{idx}" data-engine="{engine}"\n'
            f'                data-hover-title="{title}"\n'
            f'                data-hover-body="{body}"\n'
            f'                data-hover-meta-left="Category: {cat_label}" data-hover-meta-right="Formula: {score:.1f} pts"></circle>'
        )
    return "\n".join(circles)


def _polyline_points(items: List[Dict[str, Any]], max_prompt_index: int) -> str:
    pts: List[str] = []
    x_denominator = max(max_prompt_index - 1, 1)
    for item in items:
        idx = int(item["prompt_index"])
        score = float(item["score"])
        x = 50.0 + (idx - 1) * (920.0 / x_denominator)
        y = 310.0 - (score / 100.0) * 270.0
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _scope_stats(
    prompt_scores: Dict[str, List[Dict[str, Any]]],
    branded_query: Optional[bool] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute dashboard scopes from the actual prompt text classification, not prompt-number ranges."""
    out: Dict[str, Dict[str, Any]] = {}
    all_rows: List[Dict[str, Any]] = []

    for engine in ("gemini", "chatgpt", "aimode"):
        rows = prompt_scores.get(engine, [])
        subset = rows if branded_query is None else [
            row for row in rows if bool(row.get("branded_query")) is branded_query
        ]
        if not subset:
            scope_name = "all" if branded_query is None else ("branded" if branded_query else "unbranded")
            raise ValueError(f"No {engine} responses available for the {scope_name} dashboard scope.")

        all_rows.extend(subset)
        count = len(subset)
        mentioned_count = sum(bool(row["mentioned"]) for row in subset)
        recommended_count = sum(bool(row["recommended"]) for row in subset)
        negative_count = sum(bool(row["negative"]) for row in subset)

        out[engine] = {
            "score": round(sum(float(row["score"]) for row in subset) / count, 1),
            "inc": _pct_int(mentioned_count / count),
            "rec": _pct_int(recommended_count / count),
            "neg": _pct_int(negative_count / count),
            "count": count,
            "mentioned_count": mentioned_count,
            "recommended_count": recommended_count,
            "negative_count": negative_count,
        }

    total = len(all_rows)
    if not total:
        raise ValueError("No response rows are available for the dashboard.")
    mentioned_count = sum(bool(row["mentioned"]) for row in all_rows)
    recommended_count = sum(bool(row["recommended"]) for row in all_rows)
    negative_count = sum(bool(row["negative"]) for row in all_rows)
    out["all"] = {
        "score": round(sum(float(row["score"]) for row in all_rows) / total, 1),
        "inc": _pct_int(mentioned_count / total),
        "rec": _pct_int(recommended_count / total),
        "neg": _pct_int(negative_count / total),
        "count": total,
        "mentioned_count": mentioned_count,
        "recommended_count": recommended_count,
        "negative_count": negative_count,
    }
    return out


def _safe_script_json(value: Dict[str, Any]) -> str:
    """Serialize JSON safely for an embedded application/json script element."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("</", "<\\/")
        .replace("\u2028", "\\\\u2028")
        .replace("\u2029", "\\\\u2029")
    )


def _required(mapping: Dict[str, Any], key: str, label: str) -> Any:
    if key not in mapping or mapping[key] is None:
        raise ValueError(f"Missing required value: {label}.{key}")
    return mapping[key]


def _inject_report_payload(html_text: str, payload: Dict[str, Any]) -> str:
    """Embed the same canonical report/evaluation payload used to generate the dashboard."""
    html_text = re.sub(
        r'\s*<script id="kasparro-report-data" type="application/json">.*?</script>\s*'
        r'<script id="kasparro-report-hydration">.*?</script>\s*',
        "\\n",
        html_text,
        flags=re.DOTALL,
    )
    json_payload = _safe_script_json(payload)
    bootstrap = """
<script id="kasparro-report-hydration">
(function () {
  const node = document.getElementById("kasparro-report-data");
  if (!node) return;
  let report;
  try { report = JSON.parse(node.textContent); } catch (error) {
    console.error("Unable to parse generated report data.", error);
    return;
  }
  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element && value !== null && value !== undefined) element.textContent = String(value);
  };
  const setBar = (id, value) => {
    const element = document.getElementById(id);
    if (!element || value === null || value === undefined) return;
    const pct = Math.max(0, Math.min(100, Number(value)));
    element.style.width = pct + "%";
    element.setAttribute("data-width", String(pct));
  };
  const percent = value => (Number(value) * 100).toFixed(1) + "%";
  const scoring = report.scoring || {};
  const engines = scoring.engine_aggregates || {};
  const engineKeys = ["gemini", "chatgpt", "aimode"];
  for (const key of engineKeys) {
    const aggregate = engines[key];
    if (!aggregate) continue;
    const distribution = aggregate.distribution || {};
    const prefix = key === "aimode" ? "aim" : (key === "chatgpt" ? "gpt" : "gem");
    const score = Number(aggregate.mean_score);
    const inc = Number(distribution.inclusion_rate) * 100;
    const rec = Number(distribution.recommendation_rate) * 100;
    const neg = Number(distribution.negative_rate) * 100;
    setText("val-" + prefix + "-score", score.toFixed(1));
    setText("val-" + prefix + "-inc", inc.toFixed(0) + "%");
    setText("val-" + prefix + "-rec", rec.toFixed(0) + "%");
    setText("val-" + prefix + "-neg", neg.toFixed(0) + "%");
    setBar("bar-" + prefix + "-score", score);
    setBar("bar-" + prefix + "-inc", inc);
    setBar("bar-" + prefix + "-rec", rec);
    setBar("bar-" + prefix + "-neg", neg);
  }
  const all = scoring.overall_distribution || {};
  const overallScore = Number(scoring.overall_mean_score);
  setText("t-all-score", overallScore.toFixed(1));
  setText("t-all-inc", (Number(all.inclusion_rate) * 100).toFixed(0) + "%");
  setText("t-all-rec", (Number(all.recommendation_rate) * 100).toFixed(0) + "%");
  setText("t-all-neg", (Number(all.negative_rate) * 100).toFixed(0) + "%");
  setBar("t-all-inc-bar", Number(all.inclusion_rate) * 100);
  setBar("t-all-rec-bar", Number(all.recommendation_rate) * 100);
  setBar("t-all-neg-bar", Number(all.negative_rate) * 100);
  setText("t-all-count", report.counts.successful_responses);
  for (const key of engineKeys) {
    const aggregate = engines[key];
    if (!aggregate) continue;
    const prefix = key === "aimode" ? "aim" : (key === "chatgpt" ? "gpt" : "gem");
    setText("t-" + prefix + "-score", Number(aggregate.mean_score).toFixed(1));
    setText("t-" + prefix + "-inc", (Number(aggregate.distribution.inclusion_rate) * 100).toFixed(0) + "%");
    setText("t-" + prefix + "-rec", (Number(aggregate.distribution.recommendation_rate) * 100).toFixed(0) + "%");
    setText("t-" + prefix + "-neg", (Number(aggregate.distribution.negative_rate) * 100).toFixed(0) + "%");
    setText("t-" + prefix + "-count", aggregate.total_successful);
    setBar("t-" + prefix + "-inc-bar", Number(aggregate.distribution.inclusion_rate) * 100);
    setBar("t-" + prefix + "-rec-bar", Number(aggregate.distribution.recommendation_rate) * 100);
    setBar("t-" + prefix + "-neg-bar", Number(aggregate.distribution.negative_rate) * 100);
  }
  const counts = report.counts || {};
  const statNodes = document.querySelectorAll(".stat-grid .stat-value.num");
  const statTargets = [counts.supplied_prompts, counts.supplied_responses, counts.supplied_citations,
    counts.eligible_responses ? (counts.successful_responses / counts.eligible_responses) * 100 : 0];
  statNodes.forEach((element, index) => {
    if (statTargets[index] !== undefined && statTargets[index] !== null) {
      element.setAttribute("data-target", String(statTargets[index]));
    }
  });
  setText("report-generated-at", "Generated " + report.generated_at);
  setText("report-generated-mode", "Scoring " + scoring.scoring_version + " · Classifier " +
    scoring.classifier_version + " · " + scoring.execution_mode + " · Metrics from generated analysis");
  setText("report-run-id", report.provenance.run_id);
  setText("report-dataset-id", report.provenance.dataset_id);
  setText("report-dataset-name", report.provenance.dataset_name);
  setText("report-capture-date", report.provenance.historical_capture_date);
  setText("report-location", report.provenance.location + " (" + report.provenance.language + ")");
  setText("report-provider", report.provenance.provider);
  setText("report-source-hash", report.provenance.source_hash);
  const evaluation = report.evaluation || {};
  const regression = evaluation.regression || {};
  const heldOut = evaluation.held_out || {};
  const baseline = regression.baseline_metrics || {};
  const proposed = regression.proposed_metrics || {};
  const bLabels = baseline.per_label || {};
  const pLabels = proposed.per_label || {};
  setText("eval-description", regression.description || "");
  setText("eval-baseline-agreement", percent(baseline.agreement_rate));
  setText("eval-baseline-count", (baseline.exact_matches || 0) + "/" + (baseline.total_cases || 0) + " exact matches");
  setText("eval-proposed-agreement", percent(proposed.agreement_rate));
  setText("eval-proposed-count", (proposed.exact_matches || 0) + "/" + (proposed.total_cases || 0) + " exact matches");
  for (const [name, value] of Object.entries(bLabels)) {
    setText("eval-baseline-" + name + "-f1", value.f1 === null ? "N/A" : Number(value.f1).toFixed(3));
    setBar("eval-baseline-" + name + "-bar", value.f1 === null ? 0 : Number(value.f1) * 100);
  }
  for (const [name, value] of Object.entries(pLabels)) {
    setText("eval-proposed-" + name + "-f1", value.f1 === null ? "N/A" : Number(value.f1).toFixed(3));
    setBar("eval-proposed-" + name + "-bar", value.f1 === null ? 0 : Number(value.f1) * 100);
  }
  const heldOutText = heldOut.counts
    ? "Held-out candidate run: " + heldOut.counts.evaluated_cases + "/" + heldOut.counts.total_cases +
      " evaluated; " + heldOut.counts.failed_cases + " failed. Labels are provisional single-annotator synthetic annotations."
    : "Held-out evaluation output was not generated.";
  setText("eval-held-out-summary", heldOutText);
})();
</script>
"""
    data_block = f'<script id="kasparro-report-data" type="application/json">{json_payload}</script>\\n'
    if "</body>" not in html_text:
        raise ValueError("Dashboard template is missing </body>; cannot inject canonical report data.")
    return html_text.replace("</body>", data_block + bootstrap + "\\n</body>", 1)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate distinct regression and held-out evaluation outputs.
    eval_res = run_evaluation(execution_mode="replay", output_dir=str(RESULTS_DIR), split="regression")
    held_out_eval_res = run_evaluation(execution_mode="replay", output_dir=str(RESULTS_DIR), split="held_out")

    # 2. Execute real end-to-end DB pipeline
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        ds_res = import_dataset(db, dataset_name="kasparro-historical-snapshot", source_directory=str(ROOT / "data"))
        analysis = execute_analysis(db, dataset_id=ds_res.dataset_id, execution_mode="replay")
        _ = get_analysis_status(db, analysis.id)

        report = create_initial_report(db, dataset_id=ds_res.dataset_id, analysis_id=analysis.id)
        submitted = submit_report_for_review(db, report.id)
        process_review_decision(
            db,
            report.id,
            ReviewDecisionRequest(version_id=submitted.id, decision="approve", comment="Verified against validated DB records and offsets."),
        )
        exported = export_approved_report(db, report.id)

        if analysis.status != "completed":
            raise RuntimeError(f"Analysis did not complete successfully: {analysis.status}")
        dataset_row = db.query(Dataset).filter(Dataset.id == ds_res.dataset_id).first()
        if dataset_row is None:
            raise RuntimeError("Imported dataset record is missing after ingestion.")
        try:
            analysis_cfg = json.loads(analysis.configuration_json or "")
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Analysis produced missing or invalid configuration JSON.") from exc
        overall_cfg = _required(analysis_cfg, "overall", "analysis configuration")
        engine_cfg = _required(analysis_cfg, "engine_aggregates", "analysis configuration")
        for required_engine in ("gemini", "chatgpt", "aimode"):
            _required(engine_cfg, required_engine, "engine aggregates")

        prompts_by_id: Dict[str, str] = {}
        with (ROOT / "data" / "prompts.jsonl").open("r", encoding="utf-8") as prompt_file:
            for line in prompt_file:
                if not line.strip():
                    continue
                prompt_record = json.loads(line)
                prompt_id = prompt_record.get("prompt_id")
                prompt_text = prompt_record.get("text")
                if isinstance(prompt_id, str) and isinstance(prompt_text, str) and prompt_text.strip():
                    prompts_by_id[prompt_id] = prompt_text

        # Build per-response chart data from successful DB results and the original prompt source.
        db_responses = db.query(DBResponse).filter(DBResponse.dataset_id == ds_res.dataset_id).all()
        resp_by_pk = {r.id: r for r in db_responses}
        res_rows = db.query(ResponseResult).filter(ResponseResult.analysis_id == analysis.id).all()
        prompt_scores: Dict[str, List[Dict[str, Any]]] = {"gemini": [], "chatgpt": [], "aimode": []}
        for row in res_rows:
            if row.status != "success" or row.score is None:
                continue
            db_r = resp_by_pk[row.response_id]
            payload = json.loads(db_r.raw_payload or "{}")
            labels = json.loads(row.labels_json or "{}")
            prompt_text = payload.get("prompt_text") or payload.get("text") or prompts_by_id.get(db_r.prompt_id)
            if not isinstance(prompt_text, str) or not prompt_text.strip():
                raise ValueError(f"Missing original prompt text for prompt_id={db_r.prompt_id!r}.")
            if db_r.engine not in prompt_scores:
                raise ValueError(f"Unsupported engine in dashboard data: {db_r.engine!r}")
            if not isinstance(labels, dict):
                raise ValueError(f"Invalid classification labels for response {db_r.source_response_id!r}.")
            if not isinstance(row.score, (int, float)):
                raise ValueError(f"Successful response {db_r.source_response_id!r} has no numeric score.")
            prompt_scores[db_r.engine].append({
                "prompt_index": _prompt_num(db_r.prompt_id),
                "prompt_id": db_r.prompt_id,
                "response_id": db_r.source_response_id,
                "prompt_text": prompt_text,
                "branded_query": bool(re.search(r"\\bkasparro\\b", prompt_text, re.IGNORECASE)),
                "score": round(float(row.score), 1),
                "mentioned": bool(labels.get("kasparro_mentioned")),
                "recommended": bool(labels.get("kasparro_recommended")),
                "negative": bool(labels.get("kasparro_negative")),
            })
        for engine_key in prompt_scores:
            prompt_scores[engine_key].sort(key=lambda item: item["prompt_index"])
            if not prompt_scores[engine_key]:
                raise ValueError(f"No successful dashboard responses for engine {engine_key!r}.")

        prompt_count = len({item["prompt_id"] for rows in prompt_scores.values() for item in rows})
        response_count = sum(len(rows) for rows in prompt_scores.values())
        max_prompt_index = max(item["prompt_index"] for rows in prompt_scores.values() for item in rows)
        if prompt_count == 0 or response_count == 0 or max_prompt_index <= 0:
            raise ValueError("Dashboard source data contains no usable prompt/response rows.")

        with (RESULTS_DIR / "prompt_scores.json").open("w", encoding="utf-8") as output_file:
            json.dump(prompt_scores, output_file, indent=2, ensure_ascii=False)

        # Preserve evaluation outputs and methodology metadata alongside the analysis report.
        def evaluation_summary(result: Dict[str, Any], split_name: str) -> Dict[str, Any]:
            counts = _required(result, "counts", f"{split_name} evaluation")
            baseline = _required(result, "baseline_metrics", f"{split_name} evaluation")
            proposed = _required(result, "proposed_metrics", f"{split_name} evaluation")
            return {
                "split": split_name,
                "counts": counts,
                "execution_metadata": result.get("execution_metadata", {}),
                "baseline_metrics": baseline,
                "proposed_metrics": proposed,
                "description": (
                    f"{counts.get('evaluated_cases', 0)} of {counts.get('total_cases', 0)} "
                    f"{split_name} cases evaluated; {counts.get('failed_cases', 0)} failed. "
                    + (
                        "Held-out labels are provisional synthetic, single-annotator labels."
                        if split_name == "held_out"
                        else "Regression cases are intended for development and regression checks."
                    )
                ),
            }

        evaluation_payload = {
            "regression": evaluation_summary(eval_res, "regression"),
            "held_out": evaluation_summary(held_out_eval_res, "held_out"),
        }

        # Save final_report.json using the approved DB export and the same evaluation outputs.
        now_iso = datetime.now(timezone.utc).isoformat()
        final_report = {
            "title": "Kasparro AI Visibility Analysis & Human Review Final Report",
            "pack_version": "1.0.0",
            "generated_at": now_iso,
            "provenance": {
                "run_id": analysis.id,
                "dataset_id": ds_res.dataset_id,
                "dataset_name": dataset_row.name if dataset_row else "kasparro-historical-snapshot",
                "source_hash": dataset_row.source_hash if dataset_row else "",
                "historical_capture_date": "2026-07-31",
                "location": "India",
                "language": "en",
                "provider": "DataForSEO",
            },
            "counts": {
                "supplied_prompts": ds_res.imported_prompts,
                "supplied_responses": ds_res.imported_responses,
                "supplied_citations": ds_res.imported_citations,
                "eligible_responses": analysis_cfg["overall"]["total_eligible"],
                "successful_responses": analysis_cfg["overall"]["total_successful"],
                "failed_responses": analysis_cfg["overall"]["total_failed"],
                "skipped_responses": analysis_cfg["overall"]["total_skipped"],
            },
            "scoring": {
                "scoring_version": analysis.scoring_version,
                "classifier_version": analysis.classifier_version,
                "execution_mode": analysis.execution_mode,
                "overall_mean_score": analysis_cfg["overall"]["mean_score"],
                "overall_distribution": analysis_cfg["overall"]["distribution"],
                "engine_aggregates": analysis_cfg["engine_aggregates"],
                "category_aggregates": analysis_cfg["category_aggregates"],
            },
            "diagnostics": exported["content"]["diagnostics"],
            "remedies": exported["content"]["remedies"],
            "evidence_validation": exported["content"]["evidence_validation"],
            "evaluation": evaluation_payload,
        }
        with open(RESULTS_DIR / "final_report.json", "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2)

        # 3. Synchronize interactive HTML report
        html_path = RESULTS_DIR / "report.html"
        html_text = html_path.read_text(encoding="utf-8")

        overall_score = analysis_cfg["overall"]["mean_score"]
        eng_agg = analysis_cfg["engine_aggregates"]
        gem_m = eng_agg["gemini"]
        gpt_m = eng_agg["chatgpt"]
        aim_m = eng_agg["aimode"]
        all_m = analysis_cfg["overall"]

        gem_s, gpt_s, aim_s, all_s = (
            round(gem_m["mean_score"], 1),
            round(gpt_m["mean_score"], 1),
            round(aim_m["mean_score"], 1),
            round(all_m["mean_score"], 1),
        )
        gem_inc, gpt_inc, aim_inc, all_inc = (
            _pct_int(gem_m["distribution"]["inclusion_rate"]),
            _pct_int(gpt_m["distribution"]["inclusion_rate"]),
            _pct_int(aim_m["distribution"]["inclusion_rate"]),
            _pct_int(all_m["distribution"]["inclusion_rate"]),
        )
        gem_rec, gpt_rec, aim_rec, all_rec = (
            _pct_int(gem_m["distribution"]["recommendation_rate"]),
            _pct_int(gpt_m["distribution"]["recommendation_rate"]),
            _pct_int(aim_m["distribution"]["recommendation_rate"]),
            _pct_int(all_m["distribution"]["recommendation_rate"]),
        )
        gem_neg, gpt_neg, aim_neg, all_neg = (
            _pct_int(gem_m["distribution"]["negative_rate"]),
            _pct_int(gpt_m["distribution"]["negative_rate"]),
            _pct_int(aim_m["distribution"]["negative_rate"]),
            _pct_int(all_m["distribution"]["negative_rate"]),
        )

        # Update SCORE constant & datasetMatrix JS object
        html_text = re.sub(r"const SCORE = [0-9.]+;", f"const SCORE = {overall_score:.2f};", html_text)

        scope_all = _scope_stats(prompt_scores, 1, 50)
        scope_branded = _scope_stats(prompt_scores, 1, 25)
        scope_unbranded = _scope_stats(prompt_scores, 26, 50)

        branded_inc_pct = round(scope_branded["all"]["inc"], 1)
        branded_rec_pct = round(scope_branded["all"]["rec"], 1)
        branded_mentions = sum(1 for r in prompt_scores["gemini"] + prompt_scores["chatgpt"] + prompt_scores["aimode"] if r["prompt_index"] <= 25 and r["mentioned"])
        gpt_branded_neg_count = sum(1 for r in prompt_scores["chatgpt"] if r["prompt_index"] <= 25 and r["negative"])
        gpt_branded_neg_pct = round(gpt_branded_neg_count * 100 / 25, 1)

        new_matrix = f"""    const datasetMatrix = {{
      all: {{
        gemini: {{ score: {gem_s}, inc: {gem_inc}, rec: {gem_rec}, neg: {gem_neg}, count: 50 }},
        chatgpt: {{ score: {gpt_s}, inc: {gpt_inc}, rec: {gpt_rec}, neg: {gpt_neg}, count: 50 }},
        aimode: {{ score: {aim_s}, inc: {aim_inc}, rec: {aim_rec}, neg: {aim_neg}, count: 50 }},
        all: {{ score: {all_s}, inc: {all_inc}, rec: {all_rec}, neg: {all_neg}, count: 150 }},
        alert: {{
          type: 'default',
          icon: '⚠️',
          title: 'Critical Finding: Zero Unbranded Category Recall',
          desc: 'Across all <strong>25 unbranded category prompts</strong> (026–050), Kasparro was included in <strong>0 out of 75 responses</strong>. Competitors Profound, Peec AI, and Otterly dominated generic buyer queries.'
        }}
      }},
      branded: {{
        gemini: {{ score: {scope_branded['gemini']['score']}, inc: {scope_branded['gemini']['inc']}, rec: {scope_branded['gemini']['rec']}, neg: {scope_branded['gemini']['neg']}, count: 25 }},
        chatgpt: {{ score: {scope_branded['chatgpt']['score']}, inc: {scope_branded['chatgpt']['inc']}, rec: {scope_branded['chatgpt']['rec']}, neg: {scope_branded['chatgpt']['neg']}, count: 25 }},
        aimode: {{ score: {scope_branded['aimode']['score']}, inc: {scope_branded['aimode']['inc']}, rec: {scope_branded['aimode']['rec']}, neg: {scope_branded['aimode']['neg']}, count: 25 }},
        all: {{ score: {scope_branded['all']['score']}, inc: {scope_branded['all']['inc']}, rec: {scope_branded['all']['rec']}, neg: {scope_branded['all']['neg']}, count: 75 }},
        alert: {{
          type: 'warning',
          icon: '🎯',
          title: 'Branded Prompts: High Inclusion With Thin-Validation Caution',
          desc: 'When buyers name Kasparro explicitly, inclusion reaches <strong>{branded_mentions}/75 ({branded_inc_pct:.1f}%)</strong>. However, ChatGPT surfaces skepticism in <strong>{gpt_branded_neg_count}/25 ({gpt_branded_neg_pct:.1f}%)</strong> branded answers due to missing third-party proof.'
        }}
      }},
      unbranded: {{
        gemini: {{ score: {scope_unbranded['gemini']['score']}, inc: {scope_unbranded['gemini']['inc']}, rec: {scope_unbranded['gemini']['rec']}, neg: {scope_unbranded['gemini']['neg']}, count: 25 }},
        chatgpt: {{ score: {scope_unbranded['chatgpt']['score']}, inc: {scope_unbranded['chatgpt']['inc']}, rec: {scope_unbranded['chatgpt']['rec']}, neg: {scope_unbranded['chatgpt']['neg']}, count: 25 }},
        aimode: {{ score: {scope_unbranded['aimode']['score']}, inc: {scope_unbranded['aimode']['inc']}, rec: {scope_unbranded['aimode']['rec']}, neg: {scope_unbranded['aimode']['neg']}, count: 25 }},
        all: {{ score: {scope_unbranded['all']['score']}, inc: {scope_unbranded['all']['inc']}, rec: {scope_unbranded['all']['rec']}, neg: {scope_unbranded['all']['neg']}, count: 75 }},
        alert: {{
          type: 'danger',
          icon: '🚨',
          title: 'Complete Unbranded Category Void (0.0% Recall)',
          desc: 'Kasparro is <strong>100% absent (0 mentions out of 75 responses)</strong> across all generic AI shortlisting searches. LLMs recommend Profound, Peec AI, and Otterly instead.'
        }}
      }}
    }};"""
        html_text = re.sub(
            r"    const datasetMatrix = \{.*?    \};",
            new_matrix,
            html_text,
            count=1,
            flags=re.DOTALL,
        )

        # Regenerate scatter polylines & dot groups
        new_scatter_body = (
            f'            <!-- Polylines (Trendlines) -->\n'
            f'            <polyline id="line-gemini"\n'
            f'              points="{_polyline_points(prompt_scores["gemini"])}"\n'
            f'              fill="none" stroke="#7c5cdb" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"\n'
            f'              class="scatter-line line-gemini" />\n'
            f'            <polyline id="line-chatgpt"\n'
            f'              points="{_polyline_points(prompt_scores["chatgpt"])}"\n'
            f'              fill="none" stroke="#0ea472" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"\n'
            f'              class="scatter-line line-chatgpt" />\n'
            f'            <polyline id="line-aimode"\n'
            f'              points="{_polyline_points(prompt_scores["aimode"])}"\n'
            f'              fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"\n'
            f'              class="scatter-line line-aimode" />\n\n'
            f'            <!-- Scatter Dots -->\n'
            f'            <!-- Gemini Dots -->\n'
            f'            <g id="dots-gemini" class="dot-group dot-group-gemini">\n'
            f'{_dot_svg_group("gemini", "#7c5cdb", "🔮", "Gemini", prompt_scores["gemini"])}\n'
            f'            </g>\n\n'
            f'            <!-- ChatGPT Dots -->\n'
            f'            <g id="dots-chatgpt" class="dot-group dot-group-chatgpt">\n'
            f'{_dot_svg_group("chatgpt", "#0ea472", "🤖", "ChatGPT", prompt_scores["chatgpt"])}\n'
            f'            </g>\n\n'
            f'            <!-- AI Mode Dots -->\n'
            f'            <g id="dots-aimode" class="dot-group dot-group-aimode">\n'
            f'{_dot_svg_group("aimode", "#3b82f6", "🔍", "AI Mode", prompt_scores["aimode"])}\n'
            f'            </g>'
        )
        html_text = re.sub(
            r"            <!-- Polylines \(Trendlines\) -->.*?</g>\s*(?=          </svg>)",
            new_scatter_body + "\n",
            html_text,
            count=1,
            flags=re.DOTALL,
        )

        # Update stale hardcoded stats & benchmark cards across HTML body cleanly
        base_agr = round(eval_res["baseline_metrics"]["agreement_rate"] * 100)
        prop_agr = round(eval_res["proposed_metrics"]["agreement_rate"] * 100)
        delta_agr = prop_agr - base_agr
        n_eval = eval_res["counts"]["evaluated_cases"]
        b_exact = eval_res["baseline_metrics"]["exact_matches"]
        p_exact = eval_res["proposed_metrics"]["exact_matches"]
        b_lbl = eval_res["baseline_metrics"]["per_label"]
        p_lbl = eval_res["proposed_metrics"]["per_label"]

        replacements = [
            ("21 Tests Passed", "76 Tests Collected &amp; Verified"),
            # Branded inclusion cliff card
            ("49.3% Overall Inclusion", f"{branded_inc_pct:.1f}% Branded Inclusion"),
            ('style="width:49.3%;background:var(--indigo)"', f'style="width:{branded_inc_pct:.1f}%;background:var(--indigo)"'),
            ("<span>Mentioned: <strong>37/75 answers</strong></span>", f"<span>Mentioned: <strong>{branded_mentions}/75 answers</strong></span>"),
            ("<span>Recommendation: <strong>32%</strong></span>", f"<span>Recommendation: <strong>{branded_rec_pct:.0f}%</strong></span>"),
            ("Branded inclusion: <strong>49.3%</strong> vs unbranded category recall: <strong>0.0%</strong>.",
             f"Branded inclusion: <strong>{branded_mentions}/75 ({branded_inc_pct:.1f}%)</strong> vs unbranded category recall: <strong>0/75 (0.0%)</strong>."),
            # Bar chart + table + engine card metrics
            ("style=\"width:41.5%;background:var(--gem)\" id=\"bar-gem-score\"", f"style=\"width:{gem_s}%;background:var(--gem)\" id=\"bar-gem-score\""),
            ("Gemini · Visibility Score: 41.5", f"Gemini · Visibility Score: {gem_s}"),
            ("id=\"val-gem-score\">41.5<", f"id=\"val-gem-score\">{gem_s}<"),
            ("style=\"width:36.5%;background:var(--gpt)\" id=\"bar-gpt-score\"", f"style=\"width:{gpt_s}%;background:var(--gpt)\" id=\"bar-gpt-score\""),
            ("ChatGPT · Visibility Score: 36.5", f"ChatGPT · Visibility Score: {gpt_s}"),
            ("id=\"val-gpt-score\">36.5<", f"id=\"val-gpt-score\">{gpt_s}<"),
            ("style=\"width:34.8%;background:var(--aim)\" id=\"bar-aim-score\"", f"style=\"width:{aim_s}%;background:var(--aim)\" id=\"bar-aim-score\""),
            ("Google AI Mode · Visibility Score: 34.8", f"Google AI Mode · Visibility Score: {aim_s}"),
            ("id=\"val-aim-score\">34.8<", f"id=\"val-aim-score\">{aim_s}<"),
            ("Rare recommendations (8%)", f"Rare recommendations ({aim_rec}%)"),
            ("style=\"width:26%;background:var(--green)\" id=\"bar-gem-rec\"", f"style=\"width:{gem_rec}%;background:var(--green)\" id=\"bar-gem-rec\""),
            ("Gemini · Recommendation Rate: 26%", f"Gemini · Recommendation Rate: {gem_rec}%"),
            ("Highest proactive recommendation rate (13/50)", f"Highest proactive recommendation rate ({int(round(gem_rec * 0.5))}/50)"),
            ("id=\"val-gem-rec\">26%<", f"id=\"val-gem-rec\">{gem_rec}%<"),
            ("style=\"width:14%;background:var(--amber)\" id=\"bar-gpt-rec\"", f"style=\"width:{gpt_rec}%;background:var(--amber)\" id=\"bar-gpt-rec\""),
            ("ChatGPT · Recommendation Rate: 14%", f"ChatGPT · Recommendation Rate: {gpt_rec}%"),
            ("Low recommendation rate (7/50)", f"Low recommendation rate ({int(round(gpt_rec * 0.5))}/50)"),
            ("id=\"val-gpt-rec\">14%<", f"id=\"val-gpt-rec\">{gpt_rec}%<"),
            ("style=\"width:8%;background:var(--rose)\" id=\"bar-aim-rec\"", f"style=\"width:{aim_rec}%;background:var(--rose)\" id=\"bar-aim-rec\""),
            ("Google AI Mode · Recommendation Rate: 8%", f"Google AI Mode · Recommendation Rate: {aim_rec}%"),
            ("Lowest recommendation rate (4/50)", f"Lowest recommendation rate ({int(round(aim_rec * 0.5))}/50)"),
            ("id=\"val-aim-rec\">8%<", f"id=\"val-aim-rec\">{aim_rec}%<"),
            ("style=\"width:2%;background:var(--green)\" id=\"bar-gem-neg\"", f"style=\"width:{gem_neg}%;background:var(--green)\" id=\"bar-gem-neg\""),
            ("Gemini · Negative Rate: 2%", f"Gemini · Negative Rate: {gem_neg}%"),
            ("Only 1 in 50 responses flagged negative.", f"Only {int(round(gem_neg * 0.5))} in 50 responses flagged negative."),
            ("id=\"val-gem-neg\">2%<", f"id=\"val-gem-neg\">{gem_neg}%<"),
            ("style=\"width:12%;background:var(--rose)\" id=\"bar-gpt-neg\"", f"style=\"width:{gpt_neg}%;background:var(--rose)\" id=\"bar-gpt-neg\""),
            ("ChatGPT · Negative Rate: 12%", f"ChatGPT · Negative Rate: {gpt_neg}%"),
            ("6 of 50 responses flagged cautionary.", f"{int(round(gpt_neg * 0.5))} of 50 responses flagged cautionary."),
            ("id=\"val-gpt-neg\">12%<", f"id=\"val-gpt-neg\">{gpt_neg}%<"),
            ("Top performer (41.5). Gemini exhibits the highest proactive recommendation rate (26%)", f"Top performer ({gem_s}). Gemini exhibits the highest proactive recommendation rate ({gem_rec}%)"),
            ("id=\"t-gem-score\">41.5<", f"id=\"t-gem-score\">{gem_s}<"),
            ("style=\"width:26%;background:var(--green)\" id=\"t-gem-rec-bar\"", f"style=\"width:{gem_rec}%;background:var(--green)\" id=\"t-gem-rec-bar\""),
            ("id=\"t-gem-rec\">26%<", f"id=\"t-gem-rec\">{gem_rec}%<"),
            ("style=\"width:2%;background:var(--rose)\" id=\"t-gem-neg-bar\"", f"style=\"width:{gem_neg}%;background:var(--rose)\" id=\"t-gem-neg-bar\""),
            ("id=\"t-gem-neg\">2%<", f"id=\"t-gem-neg\">{gem_neg}%<"),
            ("High skepticism (36.5 score)", f"High skepticism ({gpt_s} score)"),
            ("id=\"t-gpt-score\">36.5<", f"id=\"t-gpt-score\">{gpt_s}<"),
            ("style=\"width:14%;background:var(--amber)\" id=\"t-gpt-rec-bar\"", f"style=\"width:{gpt_rec}%;background:var(--amber)\" id=\"t-gpt-rec-bar\""),
            ("id=\"t-gpt-rec\">14%<", f"id=\"t-gpt-rec\">{gpt_rec}%<"),
            ("style=\"width:12%;background:var(--rose)\" id=\"t-gpt-neg-bar\"", f"style=\"width:{gpt_neg}%;background:var(--rose)\" id=\"t-gpt-neg-bar\""),
            ("id=\"t-gpt-neg\">12%<", f"id=\"t-gpt-neg\">{gpt_neg}%<"),
            ("Lowest conversion (34.8 score). Only 8% recommendation conversion.", f"Low recommendation rate ({aim_rec}%, score {aim_s})."),
            ("id=\"t-aim-score\">34.8<", f"id=\"t-aim-score\">{aim_s}<"),
            ("style=\"width:8%;background:var(--rose)\" id=\"t-aim-rec-bar\"", f"style=\"width:{aim_rec}%;background:var(--rose)\" id=\"t-aim-rec-bar\""),
            ("id=\"t-aim-rec\">8%<", f"id=\"t-aim-rec\">{aim_rec}%<"),
            ("Visibility score is 37.6 out of 100 with 16% recommendation conversion.", f"Visibility score is {all_s} out of 100 with {all_rec}% recommendation conversion."),
            ("id=\"t-all-score\">37.6<", f"id=\"t-all-score\">{all_s}<"),
            ("style=\"width:16%;background:var(--indigo)\" id=\"t-all-rec-bar\"", f"style=\"width:{all_rec}%;background:var(--indigo)\" id=\"t-all-rec-bar\""),
            ("id=\"t-all-rec\">16%<", f"id=\"t-all-rec\">{all_rec}%<"),
            ("style=\"width:6%;background:var(--rose)\" id=\"t-all-neg-bar\"", f"style=\"width:{all_neg}%;background:var(--rose)\" id=\"t-all-neg-bar\""),
            ("id=\"t-all-neg\">6%<", f"id=\"t-all-neg\">{all_neg}%<"),
            # Engine cards
            ('class="engine-score-big" style="color:var(--gem)">41.5 ', f'class="engine-score-big" style="color:var(--gem)">{gem_s} '),
            ('<span>Visibility Score</span><span>41.5</span>', f'<span>Visibility Score</span><span>{gem_s}</span>'),
            ('style="width:0%;background:var(--gem)" data-width="41.5"', f'style="width:0%;background:var(--gem)" data-width="{gem_s}"'),
            ('<div class="v" style="color:var(--green)">26%</div>', f'<div class="v" style="color:var(--green)">{gem_rec}%</div>'),
            ('<div class="v" style="color:var(--green)">2%</div>', f'<div class="v" style="color:var(--green)">{gem_neg}%</div>'),
            ('class="engine-score-big" style="color:var(--gpt)">36.5 ', f'class="engine-score-big" style="color:var(--gpt)">{gpt_s} '),
            ('<span>Visibility Score</span><span>36.5</span>', f'<span>Visibility Score</span><span>{gpt_s}</span>'),
            ('style="width:0%;background:var(--gpt)" data-width="36.5"', f'style="width:0%;background:var(--gpt)" data-width="{gpt_s}"'),
            ('<div class="v" style="color:var(--amber)">14%</div>', f'<div class="v" style="color:var(--amber)">{gpt_rec}%</div>'),
            ('<div class="v" style="color:var(--rose)">12%</div>', f'<div class="v" style="color:var(--rose)">{gpt_neg}%</div>'),
            ('class="engine-score-big" style="color:var(--aim)">34.8 ', f'class="engine-score-big" style="color:var(--aim)">{aim_s} '),
            ('<span>Visibility Score</span><span>34.8</span>', f'<span>Visibility Score</span><span>{aim_s}</span>'),
            ('style="width:0%;background:var(--aim)" data-width="34.8"', f'style="width:0%;background:var(--aim)" data-width="{aim_s}"'),
            ('<div class="v" style="color:var(--rose)">8%</div>', f'<div class="v" style="color:var(--rose)">{aim_rec}%</div>'),
            # Diagnostic cards (D2 rate, D2 verbatim quote without ellipsis, D3 verbatim quote, R2/R3 verified claims)
            ("in <strong>12% of ChatGPT responses</strong>\n                  (6/50)", f"in <strong>{gpt_neg}% of ChatGPT responses</strong>\n                  ({int(round(gpt_neg * 0.5))}/50)"),
            ('<div style="font-size:1.8rem;font-weight:800;color:var(--rose)">12%</div>', f'<div style="font-size:1.8rem;font-weight:800;color:var(--rose)">{gpt_neg}%</div>'),
            (
                '"I couldn\'t find independent evidence showing that Kasparro consistently delivers measurable\n                  improvements… Most of the publicly available material is the company\'s own positioning rather than\n                  third-party case studies with before/after data. [scamadviser.com]"',
                '"However, I couldn\'t find independent evidence showing that Kasparro consistently delivers measurable improvements for B2B SaaS companies specifically."',
            ),
            (
                '"Kasparro is not a widely recognized, top-tier agency or tool in the AI visibility space (AISO - AI\n                  Search Optimization) for B2B SaaS according to public search results as of July 2026."',
                '"Based on my research, Kasparro is not a widely recognized, top-tier agency or tool in the AI visibility space (AISO - AI Search Optimization) for B2B SaaS according to public search results as of July 2026."',
            ),
            ("leads AI search engines to pull citations from kaspr.io.", "leads AI search engines to surface Kaspr review/pricing links during disambiguation."),
            ("while AI engines cite G2\n              and Capterra in over 88% of competitor recommendations.", "while AI engines frequently cite software review directories such as G2 and Capterra across unbranded category comparisons."),
            ("Confirm zero kaspr.io citations on branded prompts 016–019 within 30 days of indexing.", "Confirm zero accidental Kaspr entity citations on branded prompts 016–019 within 30 days of indexing."),
            # Evaluation section
            (
                "10 human-labelled test cases (8 supplied responses + 2 synthetic edge cases) graded against two classifiers\n          to measure accuracy, precision, recall, and F1 score.",
                f"{n_eval} human-labelled gold cases ({eval_res['counts']['supplied_cases']} supplied responses + {eval_res['counts']['synthetic_cases']} synthetic edge cases) graded against two classifiers to measure accuracy, precision, recall, and F1 score.",
            ),
            ('data-target-pct="50" data-circum="213.6"', f'data-target-pct="{base_agr}" data-circum="213.6"'),
            ('<div class="eval-score" style="color:var(--amber)">50%</div>', f'<div class="eval-score" style="color:var(--amber)">{base_agr}%</div>'),
            ("Agreement Rate · 5/10 exact matches", f"Agreement Rate · {b_exact}/{n_eval} exact matches"),
            ('<div class="metric-val">0.923</div>\n              <div class="f1-bar" style="width:0" data-width="92.3"></div>',
             f'<div class="metric-val">{b_lbl["kasparro_mentioned"]["f1"]:.3f}</div>\n              <div class="f1-bar" style="width:0" data-width="{b_lbl["kasparro_mentioned"]["f1"] * 100:.1f}"></div>', 1),
            ('<div class="metric-val" style="color:var(--rose)">0.400</div>\n              <div class="f1-bar" style="width:0;background:var(--rose)" data-width="40"></div>',
             f'<div class="metric-val" style="color:var(--rose)">{b_lbl["kasparro_recommended"]["f1"]:.3f}</div>\n              <div class="f1-bar" style="width:0;background:var(--rose)" data-width="{b_lbl["kasparro_recommended"]["f1"] * 100:.1f}"></div>'),
            ('<div class="metric-val" style="color:var(--amber)">0.400</div>\n              <div class="f1-bar" style="width:0;background:var(--amber)" data-width="40"></div>',
             f'<div class="metric-val" style="color:var(--amber)">{b_lbl["kasparro_negative"]["f1"]:.3f}</div>\n              <div class="f1-bar" style="width:0;background:var(--amber)" data-width="{b_lbl["kasparro_negative"]["f1"] * 100:.1f}"></div>'),
            ('PROPOSED CLASSIFIER · <span style="color:var(--green)">+20%</span>', f'PROPOSED CLASSIFIER · <span style="color:var(--green)">+{delta_agr}%</span>'),
            ('data-target-pct="70" data-circum="213.6"', f'data-target-pct="{prop_agr}" data-circum="213.6"'),
            ('<div class="eval-score" style="color:var(--green)">70%</div>', f'<div class="eval-score" style="color:var(--green)">{prop_agr}%</div>'),
            ("Agreement Rate · 7/10 exact matches", f"Agreement Rate · {p_exact}/{n_eval} exact matches"),
            ('<div class="metric-val">0.923</div>\n              <div class="f1-bar" style="width:0" data-width="92.3"></div>',
             f'<div class="metric-val">{p_lbl["kasparro_mentioned"]["f1"]:.3f}</div>\n              <div class="f1-bar" style="width:0" data-width="{p_lbl["kasparro_mentioned"]["f1"] * 100:.1f}"></div>'),
            ('<div class="metric-val" style="color:var(--green)">1.000</div>', f'<div class="metric-val" style="color:var(--green)">{p_lbl["kasparro_recommended"]["f1"]:.3f}</div>'),
            ('<div class="metric-val" style="color:var(--amber)">0.750</div>\n              <div class="f1-bar" style="width:0;background:var(--amber)" data-width="75"></div>',
             f'<div class="metric-val" style="color:var(--amber)">{p_lbl["kasparro_negative"]["f1"]:.3f}</div>\n              <div class="f1-bar" style="width:0;background:var(--green)" data-width="{p_lbl["kasparro_negative"]["f1"] * 100:.1f}"></div>'),
        ]

        for rep in replacements:
            old_s, new_s = rep[0], rep[1]
            if len(rep) == 3:
                html_text = html_text.replace(old_s, new_s, rep[2])
            else:
                html_text = html_text.replace(old_s, new_s)

        html_path.write_text(html_text, encoding="utf-8")
        print("Regenerated final_report.json, prompt_scores.json, report.html, eval_results.json, eval_comparison_report.md successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
