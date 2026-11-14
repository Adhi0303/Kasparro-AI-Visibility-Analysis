#!/usr/bin/env python3
"""Validate generated dashboard/report artifacts against source data and evaluation outputs."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
DATA = ROOT / "data"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required artifact is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required source file is missing: {path}")
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(item)
    return rows


def extract_embedded_report_data(html_text: str) -> Dict[str, Any]:
    """Return the one canonical report JSON object embedded in the HTML dashboard."""
    matches = re.findall(
        r'<script id="kasparro-report-data" type="application/json">(.*?)</script>',
        html_text,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        raise ValueError(
            "Dashboard must contain exactly one kasparro-report-data JSON payload; "
            f"found {len(matches)}."
        )
    parsed = json.loads(matches[0])
    if not isinstance(parsed, dict):
        raise ValueError("Embedded dashboard report payload must be a JSON object.")
    return parsed


def _pct(count: int, denominator: int) -> int:
    return int(round((count * 100) / denominator)) if denominator else 0


def compute_dashboard_scopes(
    prompt_scores: Mapping[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Recompute all/branded/unbranded metrics using the same grouping rules as the generator."""
    expected: Dict[str, Dict[str, Dict[str, Any]]] = {}
    engines = ("gemini", "chatgpt", "aimode")

    for scope_name, predicate in (
        ("all", lambda row: True),
        ("branded", lambda row: row.get("branded_query") is True),
        ("unbranded", lambda row: row.get("branded_query") is False),
    ):
        rows_by_engine: Dict[str, List[Dict[str, Any]]] = {}
        all_rows: List[Dict[str, Any]] = []
        for engine in engines:
            rows = prompt_scores.get(engine)
            if not isinstance(rows, list):
                raise ValueError(f"prompt_scores.json is missing engine list: {engine}")
            subset = [row for row in rows if predicate(row)]
            if not subset:
                raise ValueError(f"No {engine} rows found for dashboard scope {scope_name}.")
            rows_by_engine[engine] = subset
            all_rows.extend(subset)

        scope: Dict[str, Dict[str, Any]] = {}
        for engine in engines:
            subset = rows_by_engine[engine]
            n = len(subset)
            scope[engine] = {
                "score": round(sum(float(row["score"]) for row in subset) / n, 1),
                "inc": _pct(sum(bool(row["mentioned"]) for row in subset), n),
                "rec": _pct(sum(bool(row["recommended"]) for row in subset), n),
                "neg": _pct(sum(bool(row["negative"]) for row in subset), n),
                "count": n,
                "prompts_count": len({row["prompt_id"] for row in subset}),
            }

        n_all = len(all_rows)
        scope["all"] = {
            "score": round(sum(float(row["score"]) for row in all_rows) / n_all, 1),
            "inc": _pct(sum(bool(row["mentioned"]) for row in all_rows), n_all),
            "rec": _pct(sum(bool(row["recommended"]) for row in all_rows), n_all),
            "neg": _pct(sum(bool(row["negative"]) for row in all_rows), n_all),
            "count": n_all,
            "prompts_count": len({row["prompt_id"] for row in all_rows}),
        }
        expected[scope_name] = scope
    return expected


def validate_evidence_against_sources(
    report: Mapping[str, Any],
    source_responses: Iterable[Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    source_map: Dict[str, str] = {}
    for response in source_responses:
        response_id = response.get("response_id")
        answer_text = response.get("answer_text")
        if isinstance(response_id, str) and isinstance(answer_text, str):
            source_map[response_id] = answer_text

    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        return ["final_report.json must contain at least one diagnostic."]

    for diagnostic_index, diagnostic in enumerate(diagnostics, start=1):
        evidence = diagnostic.get("evidence") if isinstance(diagnostic, dict) else None
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"Diagnostic {diagnostic_index} has no evidence list.")
            continue

        for evidence_index, item in enumerate(evidence, start=1):
            label = f"diagnostic {diagnostic_index} evidence {evidence_index}"
            if not isinstance(item, dict):
                errors.append(f"{label} is not an object.")
                continue
            if item.get("validation_status") != "valid":
                errors.append(f"{label} is not marked as validated.")
            if item.get("location") != "answer_text":
                errors.append(f"{label} has unsupported location {item.get('location')!r}.")

            response_id = item.get("response_id")
            answer_text = source_map.get(response_id) if isinstance(response_id, str) else None
            if answer_text is None:
                errors.append(f"{label} references missing source response {response_id!r}.")
                continue

            excerpt = item.get("excerpt")
            start = item.get("start_offset")
            end = item.get("end_offset")
            if not isinstance(excerpt, str) or not excerpt:
                errors.append(f"{label} has an empty or invalid excerpt.")
                continue
            if type(start) is not int or type(end) is not int:
                errors.append(f"{label} is missing integer source offsets.")
                continue
            if start < 0 or end <= start or end > len(answer_text):
                errors.append(f"{label} has out-of-range source offsets {start}:{end}.")
                continue
            if answer_text[start:end] != excerpt:
                errors.append(f"{label} excerpt does not exactly match answer_text[{start}:{end}].")
    return errors


def validate_artifact_directory(results_dir: Path, data_dir: Path) -> List[str]:
    """Validate reports, evaluation files, scope metrics and evidence traceability."""
    errors: List[str] = []
    try:
        final_report = _load_json(results_dir / "final_report.json")
        regression = _load_json(results_dir / "eval_results.json")
        held_out = _load_json(results_dir / "eval_held_out_results.json")
        prompt_scores = _load_json(results_dir / "prompt_scores.json")
        html_text = (results_dir / "report.html").read_text(encoding="utf-8")
        source_responses = _load_jsonl(data_dir / "responses.jsonl")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]

    try:
        embedded = extract_embedded_report_data(html_text)
        if embedded != final_report:
            errors.append("Embedded dashboard report payload differs from final_report.json.")
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    if final_report.get("counts", {}).get("supplied_responses") != len(source_responses):
        errors.append("final_report supplied_responses count does not match data/responses.jsonl.")

    evidence_errors = validate_evidence_against_sources(final_report, source_responses)
    errors.extend(evidence_errors)

    report_evaluation = final_report.get("evaluation", {})
    for split_name, evaluation_data in (("regression", regression), ("held_out", held_out)):
        embedded_eval = report_evaluation.get(split_name)
        if not isinstance(embedded_eval, dict):
            errors.append(f"final_report.json is missing evaluation.{split_name}.")
            continue
        if embedded_eval.get("counts") != evaluation_data.get("counts"):
            errors.append(f"final_report evaluation.{split_name} counts differ from its evaluation JSON.")
        if embedded_eval.get("baseline_metrics") != evaluation_data.get("baseline_metrics"):
            errors.append(f"final_report evaluation.{split_name} baseline metrics differ from its evaluation JSON.")
        if embedded_eval.get("proposed_metrics") != evaluation_data.get("proposed_metrics"):
            errors.append(f"final_report evaluation.{split_name} proposed metrics differ from its evaluation JSON.")

    actual_eval = final_report.get("evaluation", {}).get("regression", {}).get("counts", {})
    if actual_eval.get("split") not in (None, "regression"):
        errors.append("Regression result metadata has an unexpected split name.")
    held_counts = final_report.get("evaluation", {}).get("held_out", {}).get("counts", {})
    if held_counts.get("split") != "held_out":
        errors.append("Held-out result metadata is not marked split=held_out.")

    try:
        expected_scopes = compute_dashboard_scopes(prompt_scores)
        report_scopes = final_report.get("dashboard_scopes", {})
        for scope_name, engines in expected_scopes.items():
            for engine_name, expected_metrics in engines.items():
                stored_metrics = report_scopes.get(scope_name, {}).get(engine_name, {})
                for metric_name, expected_value in expected_metrics.items():
                    if stored_metrics.get(metric_name) != expected_value:
                        errors.append(
                            f"final_report dashboard_scopes.{scope_name}.{engine_name}.{metric_name} "
                            "does not match prompt_scores.json."
                        )
        matrix_match = re.search(r"const datasetMatrix\s*=\s*(\{.*?\});", html_text, flags=re.DOTALL)
        if not matrix_match:
            errors.append("Dashboard is missing its generated datasetMatrix.")
        else:
            matrix = json.loads(matrix_match.group(1))
            for scope_name, engines in expected_scopes.items():
                for engine_name, expected_metrics in engines.items():
                    actual_metrics = matrix.get(scope_name, {}).get(engine_name, {})
                    for metric_name, expected_value in expected_metrics.items():
                        if actual_metrics.get(metric_name) != expected_value:
                            errors.append(
                                f"Dashboard {scope_name}.{engine_name}.{metric_name} "
                                f"does not match prompt_scores.json."
                            )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"Unable to verify dashboard scope metrics: {exc}")

    required_markers = (
        'id="kasparro-report-data"',
        'id="kasparro-report-hydration"',
        'id="diagnostics-container"',
        'id="remedies-container"',
        'id="eval-held-out-summary"',
        'id="report-generated-mode"',
    )
    for marker in required_markers:
        if marker not in html_text:
            errors.append(f"Dashboard is missing required dynamic element: {marker}")

    stale_markers = (
        "76 Tests Collected",
        "21/21 Tests Pass",
        "Tests Collected &amp; Verified",
        "37.57",
    )
    for marker in stale_markers:
        if marker in html_text:
            errors.append(f"Dashboard contains stale hardcoded claim: {marker}")

    prompt_score_count = sum(len(rows) for rows in prompt_scores.values() if isinstance(rows, list))
    expected_successful = final_report.get("counts", {}).get("successful_responses")
    if prompt_score_count != expected_successful:
        errors.append(
            f"prompt_scores.json contains {prompt_score_count} rows but final_report says "
            f"{expected_successful} successful responses."
        )

    return errors


def main() -> int:
    try:
        errors = validate_artifact_directory(RESULTS, DATA)
    except Exception as exc:
        print(f"ARTIFACT VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("ARTIFACT VALIDATION FAILED:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("ARTIFACT VALIDATION PASSED.")
    print("Dashboard payload, report metrics, evaluation outputs, prompt scopes and verbatim evidence are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
