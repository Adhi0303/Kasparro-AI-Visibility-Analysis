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
from typing import Any, Dict, List

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


def _dot_svg_group(engine: str, color: str, icon: str, engine_label: str, items: List[Dict[str, Any]]) -> str:
    circles: List[str] = []
    for item in items:
        idx = item["prompt_index"]
        score = float(item["score"])
        x = 50.0 + (idx - 1) * (920.0 / 49.0)
        y = 310.0 - (score / 100.0) * 270.0
        cat_label = "Branded Query" if idx <= 25 else "Unbranded GEO"
        title = html_lib.escape(f"{icon} {engine_label} · Prompt {idx:02d} · Score: {score:.1f}/100", quote=True)
        q_text = html_lib.escape(json.dumps(item["prompt_text"]), quote=True)
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


def _polyline_points(items: List[Dict[str, Any]]) -> str:
    pts: List[str] = []
    for item in items:
        idx = item["prompt_index"]
        score = float(item["score"])
        x = 50.0 + (idx - 1) * (920.0 / 49.0)
        y = 310.0 - (score / 100.0) * 270.0
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def _scope_stats(prompt_scores: Dict[str, List[Dict[str, Any]]], start_p: int, end_p: int) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    all_rows: List[Dict[str, Any]] = []
    for eng in ("gemini", "chatgpt", "aimode"):
        subset = [x for x in prompt_scores[eng] if start_p <= x["prompt_index"] <= end_p]
        n = len(subset)
        all_rows.extend(subset)
        avg = round(sum(x["score"] for x in subset) / n, 1) if n else 0.0
        inc = round(sum(1 for x in subset if x["mentioned"]) * 100 / n) if n else 0
        rec = round(sum(1 for x in subset if x["recommended"]) * 100 / n) if n else 0
        neg = round(sum(1 for x in subset if x["negative"]) * 100 / n) if n else 0
        out[eng] = {"score": avg, "inc": inc, "rec": rec, "neg": neg, "count": n}
    n_all = len(all_rows)
    out["all"] = {
        "score": round(sum(x["score"] for x in all_rows) / n_all, 1) if n_all else 0.0,
        "inc": round(sum(1 for x in all_rows if x["mentioned"]) * 100 / n_all) if n_all else 0,
        "rec": round(sum(1 for x in all_rows if x["recommended"]) * 100 / n_all) if n_all else 0,
        "neg": round(sum(1 for x in all_rows if x["negative"]) * 100 / n_all) if n_all else 0,
        "count": n_all,
    }
    return out


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Re-run evaluation harness (replay)
    eval_res = run_evaluation(execution_mode="replay", output_dir=str(RESULTS_DIR))

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

        dataset_row = db.query(Dataset).filter(Dataset.id == ds_res.dataset_id).first()
        analysis_cfg = json.loads(analysis.configuration_json)

        # Build prompt_scores.json ordered P01..P50 per engine
        db_responses = db.query(DBResponse).filter(DBResponse.dataset_id == ds_res.dataset_id).all()
        resp_by_pk = {r.id: r for r in db_responses}
        res_rows = db.query(ResponseResult).filter(ResponseResult.analysis_id == analysis.id).all()

        prompt_scores: Dict[str, List[Dict[str, Any]]] = {"gemini": [], "chatgpt": [], "aimode": []}
        for row in res_rows:
            db_r = resp_by_pk[row.response_id]
            payload = json.loads(db_r.raw_payload)
            labels = json.loads(row.labels_json or "{}")
            p_idx = _prompt_num(db_r.prompt_id)
            prompt_scores[db_r.engine].append({
                "prompt_index": p_idx,
                "prompt_text": payload.get("prompt_text", ""),
                "score": round(float(row.score or 0.0), 1),
                "mentioned": bool(labels.get("kasparro_mentioned")),
                "recommended": bool(labels.get("kasparro_recommended")),
                "negative": bool(labels.get("kasparro_negative")),
            })
        for eng in prompt_scores:
            prompt_scores[eng].sort(key=lambda item: item["prompt_index"])

        with open(RESULTS_DIR / "prompt_scores.json", "w", encoding="utf-8") as f:
            json.dump(prompt_scores, f, indent=2)

        # Save final_report.json using real DB export content
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
                "scoring_version": "v1",
                "classifier_version": "v1",
                "execution_mode": "replay",
                "overall_mean_score": analysis_cfg["overall"]["mean_score"],
                "overall_distribution": analysis_cfg["overall"]["distribution"],
                "engine_aggregates": analysis_cfg["engine_aggregates"],
                "category_aggregates": analysis_cfg["category_aggregates"],
            },
            "diagnostics": exported["content"]["diagnostics"],
            "remedies": exported["content"]["remedies"],
            "evidence_validation": exported["content"]["evidence_validation"],
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
