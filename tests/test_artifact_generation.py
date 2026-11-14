import pytest

from demo import require_number, require_rate
from tools.regenerate_artifacts import render_dashboard_html


def _report():
    distribution = {
        "inclusion_rate": 0.5,
        "recommendation_rate": 0.25,
        "negative_rate": 0.1,
    }
    engine_aggregates = {
        engine: {
            "mean_score": score,
            "distribution": distribution,
        }
        for engine, score in (("gemini", 42.0), ("chatgpt", 38.5), ("aimode", 40.25))
    }
    return {
        "generated_at": "2026-11-14T10:00:00+00:00",
        "provenance": {
            "historical_capture_date": "2026-07-31",
            "location": "India",
            "language": "en",
            "dataset_name": "test-dataset",
            "source_hash": "test-hash",
            "run_id": "run-test",
            "dataset_id": "dataset-test",
        },
        "counts": {
            "supplied_prompts": 2,
            "supplied_responses": 6,
            "supplied_citations": 9,
            "eligible_responses": 6,
            "successful_responses": 5,
            "failed_responses": 1,
            "skipped_responses": 0,
        },
        "scoring": {
            "execution_mode": "replay",
            "scoring_version": "v1",
            "classifier_version": "v2",
            "overall_mean_score": 39.5,
            "overall_distribution": distribution,
            "engine_aggregates": engine_aggregates,
        },
        "diagnostics": [
            {
                "title": "Evidence integrity finding",
                "observed_pattern": "A supported pattern.",
                "comparison": "A data-derived comparison.",
                "evidence": [
                    {
                        "response_id": "response-1",
                        "engine": "chatgpt",
                        "location": "answer_text",
                        "start_offset": 4,
                        "end_offset": 23,
                        "excerpt": "<script>alert(1)</script>",
                    }
                ],
            }
        ],
        "remedies": [{"title": "Improve verified case studies", "description": "Publish independent results."}],
    }


def _evaluation():
    per_label = {
        label: {"precision": 0.8, "recall": 0.75, "f1": 0.77}
        for label in (
            "kasparro_mentioned",
            "kasparro_recommended",
            "kasparro_negative",
        )
    }
    return {
        "counts": {
            "total_cases": 20,
            "evaluated_cases": 19,
            "failed_cases": 1,
        },
        "baseline_metrics": {
            "agreement_rate": 0.5,
            "per_label": per_label,
        },
        "proposed_metrics": {
            "agreement_rate": 0.8,
            "per_label": per_label,
        },
    }


def _prompt_scores():
    row = {
        "status": "success",
        "score": 39.5,
        "mentioned": True,
        "recommended": False,
        "negative": False,
        "is_branded_prompt": True,
    }
    return {
        "gemini": [row],
        "chatgpt": [row],
        "aimode": [row],
    }


def test_dashboard_uses_current_analysis_and_evaluation_values():
    html = render_dashboard_html(_report(), _evaluation(), _prompt_scores())

    assert "39.50 / 100" in html
    assert "42.0" in html
    assert "38.5" in html
    assert "40.2" in html
    assert "50.0%" in html
    assert "80.0%" in html
    assert "19 / 1" in html
    assert "6" in html and "9" in html
    assert "76 Tests Collected" not in html
    assert "21/21 Tests Pass" not in html
    assert "37.57" not in html


def test_dashboard_escapes_untrusted_evidence_text():
    html = render_dashboard_html(_report(), _evaluation(), _prompt_scores())

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html


def test_dashboard_fails_when_required_metrics_are_missing():
    report = _report()
    del report["scoring"]["engine_aggregates"]["chatgpt"]

    with pytest.raises(RuntimeError, match="engine_aggregates.chatgpt"):
        render_dashboard_html(report, _evaluation(), _prompt_scores())


def test_dashboard_fails_when_response_counts_do_not_reconcile():
    report = _report()
    report["counts"]["successful_responses"] = 4

    with pytest.raises(RuntimeError, match="counts are inconsistent"):
        render_dashboard_html(report, _evaluation(), _prompt_scores())


def test_demo_metric_helpers_reject_missing_or_invalid_values():
    with pytest.raises(RuntimeError, match="missing or non-numeric"):
        require_number(None, "overall.mean_score")

    with pytest.raises(RuntimeError, match="outside its valid range"):
        require_number(1.5, "distribution.inclusion_rate", minimum=0, maximum=1)

    assert require_number(0, "overall.mean_score") == 0
    assert require_rate({"inclusion_rate": 0.5}, "inclusion_rate", "overall") == 0.5


def test_dashboard_handles_empty_prompt_cohort_as_unavailable():
    scores = {"gemini": [], "chatgpt": [], "aimode": []}
    html = render_dashboard_html(_report(), _evaluation(), scores)

    assert "N/A" in html
    assert "0</td>" in html
