import html
import json
from pathlib import Path
from collections import defaultdict

import pytest

from app.categories import categorize_prompt, CATEGORIES


@pytest.fixture(scope="module")
def dataset_and_reports():
    repo = Path(__file__).resolve().parent.parent
    prompts_file = repo / "data" / "prompts.jsonl"
    responses_file = repo / "data" / "responses.jsonl"
    final_report_file = repo / "evaluation" / "results" / "final_report.json"
    prompt_scores_file = repo / "evaluation" / "results" / "prompt_scores.json"
    report_html_file = repo / "evaluation" / "results" / "report.html"

    prompts = [json.loads(line) for line in prompts_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    responses = [json.loads(line) for line in responses_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    final_report = json.loads(final_report_file.read_text(encoding="utf-8"))
    prompt_scores = json.loads(prompt_scores_file.read_text(encoding="utf-8"))
    report_html = report_html_file.read_text(encoding="utf-8")

    return {
        "prompts": prompts,
        "responses": responses,
        "final_report": final_report,
        "prompt_scores": prompt_scores,
        "report_html": report_html,
    }


def test_p4_reconcile_all_150_archived_responses(dataset_and_reports):
    prompts = dataset_and_reports["prompts"]
    responses = dataset_and_reports["responses"]
    final_report = dataset_and_reports["final_report"]
    prompt_scores = dataset_and_reports["prompt_scores"]

    # 1. Total counts
    assert len(prompts) == 50
    assert len(responses) == 150

    # 2. Per-engine response counts
    by_engine = defaultdict(list)
    for r in responses:
        by_engine[r["engine"]].append(r)
    assert len(by_engine["chatgpt"]) == 50
    assert len(by_engine["gemini"]) == 50
    assert len(by_engine["aimode"]) == 50

    # 3. Unique response IDs
    response_ids = [r["response_id"] for r in responses]
    assert len(set(response_ids)) == 150

    # 4. prompt_scores response accounting
    scores_by_engine = {
        eng: prompt_scores.get(eng, []) for eng in ("chatgpt", "gemini", "aimode")
    }
    assert len(scores_by_engine["chatgpt"]) == 50
    assert len(scores_by_engine["gemini"]) == 50
    assert len(scores_by_engine["aimode"]) == 50

    scored_rids = set()
    for eng, items in scores_by_engine.items():
        for item in items:
            scored_rids.add(item["response_id"])
            assert item["status"] == "success"
    assert scored_rids == set(response_ids)

    # 5. final_report counts reconciliation
    counts = final_report["counts"]
    assert counts["supplied_prompts"] == 50
    assert counts["supplied_responses"] == 150
    assert counts["eligible_responses"] == 150
    assert counts["successful_responses"] == 150
    assert counts["failed_responses"] == 0
    assert counts["skipped_responses"] == 0


def test_p4_recalculate_aggregates_against_final_report(dataset_and_reports):
    prompts = dataset_and_reports["prompts"]
    prompt_scores = dataset_and_reports["prompt_scores"]
    final_report = dataset_and_reports["final_report"]

    prompts_map = {p["prompt_id"]: p.get("text", "") for p in prompts}

    all_items = []
    for eng in ("chatgpt", "gemini", "aimode"):
        for item in prompt_scores.get(eng, []):
            item_c = dict(item)
            item_c["category"] = categorize_prompt(prompts_map.get(item["prompt_id"], ""))
            all_items.append(item_c)

    assert len(all_items) == 150

    # Overall calculation
    scores = [it["score"] for it in all_items]
    mean_score = round(sum(scores) / len(scores), 2)
    inclusion_rate = round(sum(1 for it in all_items if it.get("mentioned")) / len(all_items), 4)
    recommendation_rate = round(sum(1 for it in all_items if it.get("recommended")) / len(all_items), 4)
    negative_rate = round(sum(1 for it in all_items if it.get("negative")) / len(all_items), 4)

    rep_scoring = final_report["scoring"]
    assert rep_scoring["overall_mean_score"] == mean_score == 33.04
    assert rep_scoring["overall_distribution"]["inclusion_rate"] == inclusion_rate == 0.48
    assert rep_scoring["overall_distribution"]["recommendation_rate"] == recommendation_rate == 0.06
    assert rep_scoring["overall_distribution"]["negative_rate"] == negative_rate == 0.0333

    # Engine aggregates
    for eng in ("chatgpt", "gemini", "aimode"):
        eng_items = [it for it in all_items if it["engine"] == eng]
        eng_scores = [it["score"] for it in eng_items]
        eng_mean = round(sum(eng_scores) / len(eng_items), 2)
        eng_inc = round(sum(1 for it in eng_items if it.get("mentioned")) / len(eng_items), 4)
        eng_rec = round(sum(1 for it in eng_items if it.get("recommended")) / len(eng_items), 4)
        eng_neg = round(sum(1 for it in eng_items if it.get("negative")) / len(eng_items), 4)

        rep_eng = rep_scoring["engine_aggregates"][eng]
        assert rep_eng["mean_score"] == eng_mean
        assert rep_eng["distribution"]["inclusion_rate"] == eng_inc
        assert rep_eng["distribution"]["recommendation_rate"] == eng_rec
        assert rep_eng["distribution"]["negative_rate"] == eng_neg

    # Category aggregates
    for cat in CATEGORIES:
        cat_items = [it for it in all_items if it["category"] == cat]
        assert len(cat_items) > 0
        cat_scores = [it["score"] for it in cat_items]
        cat_mean = round(sum(cat_scores) / len(cat_items), 2)
        cat_inc = round(sum(1 for it in cat_items if it.get("mentioned")) / len(cat_items), 4)
        cat_rec = round(sum(1 for it in cat_items if it.get("recommended")) / len(cat_items), 4)
        cat_neg = round(sum(1 for it in cat_items if it.get("negative")) / len(cat_items), 4)

        rep_cat = rep_scoring["category_aggregates"][cat]
        assert rep_cat["mean_score"] == cat_mean
        assert rep_cat["distribution"]["inclusion_rate"] == cat_inc
        assert rep_cat["distribution"]["recommendation_rate"] == cat_rec
        assert rep_cat["distribution"]["negative_rate"] == cat_neg


def test_p4_diagnostics_and_remedies_structure_and_rendering(dataset_and_reports):
    final_report = dataset_and_reports["final_report"]
    report_html = dataset_and_reports["report_html"]

    diagnostics = final_report["diagnostics"]
    assert len(diagnostics) == 3
    for diag in diagnostics:
        assert diag["title"]
        assert diag["observed_pattern"]
        assert len(diag["evidence"]) >= 2
        for ev in diag["evidence"]:
            assert ev["response_id"]
            assert ev["excerpt"]
            assert ev["location"] == "answer_text"
            assert isinstance(ev["start_offset"], int)
            assert isinstance(ev["end_offset"], int)

    remedies = final_report["remedies"]
    assert len(remedies) == 3
    for rem in remedies:
        assert rem["title"]
        assert rem["problem"]
        assert len(rem["supporting_evidence"]) >= 2
        assert rem["action"]
        assert rem["expected_benefit"]
        assert rem["effort"]
        assert rem["uncertainty"]
        assert rem["validation"]

        # Check rendered in report.html (accounting for HTML escaping of & and quotes)
        assert html.escape(rem["title"]) in report_html
        assert html.escape(rem["action"]) in report_html
        assert html.escape(rem["validation"]) in report_html
