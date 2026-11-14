import json

import pytest

from tools.validate_artifacts import (
    compute_dashboard_scopes,
    extract_embedded_report_data,
    validate_artifact_directory,
    validate_evidence_against_sources,
)


def _sample_rows():
    rows = {"gemini": [], "chatgpt": [], "aimode": []}
    for engine in rows:
        rows[engine].append({
            "prompt_id": "p-branded",
            "branded_query": True,
            "score": 60.0,
            "mentioned": True,
            "recommended": True,
            "negative": False,
        })
        rows[engine].append({
            "prompt_id": "p-unbranded",
            "branded_query": False,
            "score": 20.0,
            "mentioned": False,
            "recommended": False,
            "negative": False,
        })
    return rows


def _sample_report(source_text):
    rows = _sample_rows()
    scopes = compute_dashboard_scopes(rows)
    metrics = {
        "total_cases": 2,
        "evaluated_cases": 2,
        "failed_cases": 0,
        "exact_matches": 2,
        "agreement_rate": 1.0,
        "per_label": {},
        "split": "regression",
    }
    held_metrics = {**metrics, "split": "held_out"}


    return {
        "title": "Test report",
        "generated_at": "2026-11-14T00:00:00+00:00",
        "provenance": {
            "run_id": "run-1",
            "dataset_id": "dataset-1",
            "dataset_name": "test",
            "source_hash": "abc",
            "historical_capture_date": "2026-07-31",
            "location": "India",
            "language": "en",
            "provider": "DataForSEO",
        },
        "counts": {
            "supplied_prompts": 2,
            "supplied_responses": 6,
            "supplied_citations": 0,
            "eligible_responses": 6,
            "successful_responses": 6,
            "failed_responses": 0,
            "skipped_responses": 0,
        },
        "scoring": {
            "scoring_version": "v1",
            "classifier_version": "v1",
            "execution_mode": "replay",
            "overall_mean_score": 40.0,
            "overall_distribution": {
                "inclusion_rate": 0.5,
                "recommendation_rate": 0.5,
                "negative_rate": 0.0,
            },
            "engine_aggregates": {
                engine: {
                    "mean_score": 40.0,
                    "total_successful": 2,
                    "distribution": {
                        "inclusion_rate": 0.5,
                        "recommendation_rate": 0.5,
                        "negative_rate": 0.0,
                    },
                }
                for engine in ("gemini", "chatgpt", "aimode")
            },
            "category_aggregates": {},
        },
        "diagnostics": [{
            "title": "Source finding",
            "observed_pattern": "Kasparro is mentioned.",
            "evidence": [{
                "response_id": "resp-1",
                "engine": "gemini",
                "prompt": "p-branded",
                "excerpt": source_text,
                "location": "answer_text",
                "start_offset": 0,
                "end_offset": len(source_text),
                "match_type": "exact",
                "validation_status": "valid",
            }],
        }],
        "remedies": [],
        "evidence_validation": {},
        "dashboard_scopes": {
            "all": scopes["all"],
            "branded": scopes["branded"],
            "unbranded": scopes["unbranded"],
            "competitors": "See diagnostics",
        },
        "evaluation": {
            "regression": {
                "counts": metrics,
                "baseline_metrics": {"total_cases": 2, "exact_matches": 1, "agreement_rate": 0.5, "per_label": {}},
                "proposed_metrics": {"total_cases": 2, "exact_matches": 2, "agreement_rate": 1.0, "per_label": {}},
            },
            "held_out": {
                "counts": held_metrics,
                "baseline_metrics": {"total_cases": 2, "exact_matches": 1, "agreement_rate": 0.5, "per_label": {}},
                "proposed_metrics": {"total_cases": 2, "exact_matches": 2, "agreement_rate": 1.0, "per_label": {}},
            },
        },
    }


def test_embedded_report_payload_requires_exactly_one_json_script():
    payload = {"counts": {"successful_responses": 1}}
    html = (
        '<html><body><script id="kasparro-report-data" type="application/json">'
        + json.dumps(payload)
        + "</script></body></html>"
    )
    assert extract_embedded_report_data(html) == payload
    with pytest.raises(ValueError, match="exactly one"):
        extract_embedded_report_data("<html></html>")


def test_dashboard_scope_metrics_are_recomputed_from_prompt_scores():
    scopes = compute_dashboard_scopes(_sample_rows())
    assert scopes["all"]["all"]["count"] == 6
    assert scopes["all"]["all"]["prompts_count"] == 2
    assert scopes["branded"]["all"]["inc"] == 100
    assert scopes["unbranded"]["all"]["inc"] == 0
    assert scopes["branded"]["gemini"]["score"] == 60.0
    assert scopes["unbranded"]["chatgpt"]["count"] == 1


def test_evidence_validator_rejects_wrong_source_offsets():
    source = "Kasparro appears in this response."
    report = _sample_report(source)
    responses = [{"response_id": "resp-1", "answer_text": source}]
    assert validate_evidence_against_sources(report, responses) == []

    report["diagnostics"][0]["evidence"][0]["start_offset"] = 1
    errors = validate_evidence_against_sources(report, responses)
    assert any("does not exactly match" in error for error in errors)


def test_artifact_validator_checks_dashboard_report_eval_and_evidence(tmp_path):
    results = tmp_path / "results"
    data = tmp_path / "data"
    results.mkdir()
    data.mkdir()

    source = "Kasparro appears in this response."
    responses = [
        {"response_id": "resp-1", "answer_text": source},
        {"response_id": "resp-2", "answer_text": "No brand mention."},
        {"response_id": "resp-3", "answer_text": "No brand mention."},
        {"response_id": "resp-4", "answer_text": "No brand mention."},
        {"response_id": "resp-5", "answer_text": "No brand mention."},
        {"response_id": "resp-6", "answer_text": "No brand mention."},
    ]
    (data / "responses.jsonl").write_text(
        "\n".join(json.dumps(row) for row in responses) + "\n",
        encoding="utf-8",
    )

    prompt_scores = _sample_rows()
    report = _sample_report(source)
    eval_reg = report["evaluation"]["regression"]
    eval_held = report["evaluation"]["held_out"]

    matrix = {}
    for scope_name, scope in report["dashboard_scopes"].items():
        if scope_name == "competitors":
            continue
        matrix[scope_name] = {}
        for engine, metrics in scope.items():
            matrix[scope_name][engine] = {
                "score": metrics["score"],
                "inc": metrics["inc"],
                "rec": metrics["rec"],
                "neg": metrics["neg"],
                "count": metrics["count"],
                "prompts_count": metrics["prompts_count"],
            }
    matrix["all"]["alert"] = {"type": "warning", "icon": "i", "title": "Test", "desc": "Test"}

    files = {
        "final_report.json": report,
        "prompt_scores.json": prompt_scores,
        "eval_results.json": {
            "counts": eval_reg["counts"],
            "baseline_metrics": eval_reg["baseline_metrics"],
            "proposed_metrics": eval_reg["proposed_metrics"],
        },
        "eval_held_out_results.json": {
            "counts": eval_held["counts"],
            "baseline_metrics": eval_held["baseline_metrics"],
            "proposed_metrics": eval_held["proposed_metrics"],
        },
    }
    for name, value in files.items():
        (results / name).write_text(json.dumps(value), encoding="utf-8")

    html = (
        '<html><body>'
        '<div id="diagnostics-container"></div><div id="remedies-container"></div>'
        '<div id="eval-held-out-summary"></div><div id="report-generated-mode"></div>'
        '<script id="kasparro-report-data" type="application/json">'
        + json.dumps(report)
        + '</script><script id="kasparro-report-hydration"></script>'
        + "const datasetMatrix = " + json.dumps(matrix) + ";"
        + '</body></html>'
    )
    (results / "report.html").write_text(html, encoding="utf-8")

    assert validate_artifact_directory(results, data) == []

    # A stale visible metric must fail validation.
    (results / "report.html").write_text(html + "76 Tests Collected", encoding="utf-8")
    errors = validate_artifact_directory(results, data)
    assert any("stale hardcoded claim" in error for error in errors)



def test_demo_metric_helpers_reject_missing_or_invalid_fallback_values():
    from demo import require_mapping, require_number, require_rate

    assert require_mapping({"score": 12}, "metrics") == {"score": 12}
    assert require_number({"score": 12}, "score", "metrics") == 12.0
    assert require_rate({"rate": 0.75}, "rate", "metrics") == 0.75

    with pytest.raises(RuntimeError):
        require_mapping(None, "metrics")
    with pytest.raises(RuntimeError):
        require_number({}, "score", "metrics")
    with pytest.raises(RuntimeError):
        require_number({"score": float("nan")}, "score", "metrics")
    with pytest.raises(RuntimeError):
        require_rate({"rate": 1.5}, "rate", "metrics")


def test_demo_manifest_count_keys_match_assignment_pack():
    from pathlib import Path
    from demo import require_mapping, require_number

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "PACK_MANIFEST.json").read_text(encoding="utf-8"))
    counts = require_mapping(manifest.get("counts"), "pack counts")
    assert require_number(counts, "prompts", "pack counts") > 0
    assert require_number(counts, "responses", "pack counts") > 0
    assert require_number(counts, "citation_entries", "pack counts") > 0
