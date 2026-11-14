"""Repeated-run stability study for the real-model provider on a frozen split.

This is an optional reliability experiment, not a substitute for the primary
single-pass benchmark. It records per-case label stability, failures and latency.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.run_eval import load_cases, load_response_texts, load_response_prompt_texts
from evaluation.grader import baseline_classify, grade_predictions
from app.config import get_settings
from app.llm.provider import ProviderClassifier


def run_repeatability(
    *,
    split: str = "regression",
    repeats: int = 3,
    cases_path: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    if repeats < 2 or repeats > 10:
        raise ValueError("repeats must be between 2 and 10")
    if split not in ("regression", "held_out"):
        raise ValueError("split must be regression or held_out")
    cases_path = cases_path or (
        "evaluation/cases.jsonl" if split == "regression"
        else "evaluation/held_out_cases.jsonl"
    )
    cases = load_cases(cases_path)
    settings = get_settings()
    classifier = ProviderClassifier(settings)
    if not settings.LLM_API_KEY or not settings.LLM_API_KEY.strip():
        raise ValueError("LLM_API_KEY is required for a real-model repeatability study.")
    if settings.EXECUTION_MODE != "real_model":
        raise ValueError("Set EXECUTION_MODE=real_model in the local .env.")

    texts = load_response_texts()
    prompts = load_response_prompt_texts()
    import inspect
    signature = inspect.signature(classifier.classify)
    accepts_prompt = "prompt_text" in signature.parameters or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()
    )

    baseline_all = []
    expected_all = []
    case_runs: dict[str, list[dict[str, Any]]] = {}
    latencies: list[float] = []
    for case in cases:
        case_id = case["case_id"]
        response_id = case.get("response_id") or case_id
        synthetic = case.get("source_type") in ("synthetic", "held_out_synthetic")
        answer = case.get("synthetic_text", "") if synthetic else texts.get(response_id, "")
        prompt = case.get("prompt_text") if synthetic else prompts.get(response_id)
        if not answer.strip():
            raise ValueError(f"{case_id}: archived/synthetic answer text is missing")
        expected = case["expected"]
        baseline_all.append(baseline_classify(answer))
        expected_all.append(expected)
        case_runs[case_id] = []
        for repeat_index in range(1, repeats + 1):
            kwargs = {
                "response_id": response_id,
                "engine": case.get("engine", "unknown"),
                "answer_text": answer,
            }
            if accepts_prompt:
                kwargs["prompt_text"] = prompt or None
            started = time.perf_counter()
            result = classifier.classify(**kwargs)
            elapsed = round(time.perf_counter() - started, 4)
            latencies.append(elapsed)
            prediction = None
            if result.status == "success":
                prediction = {
                    "kasparro_mentioned": result.kasparro_mentioned,
                    "kasparro_recommended": result.kasparro_recommended,
                    "kasparro_negative": result.kasparro_negative,
                }
            case_runs[case_id].append({
                "repeat": repeat_index,
                "status": result.status,
                "prediction": prediction,
                "failure_reason": result.failure_reason,
                "latency_seconds": elapsed,
            })

    all_calls = [call for runs in case_runs.values() for call in runs]
    successful = [call for call in all_calls if call["status"] == "success"]
    failed = [call for call in all_calls if call["status"] != "success"]
    per_repeat = []
    for index in range(repeats):
        successful_cases = [
            (case["expected"], case_runs[case["case_id"]][index]["prediction"])
            for case in cases
            if case_runs[case["case_id"]][index]["status"] == "success"
        ]
        expected = [pair[0] for pair in successful_cases]
        predicted = [pair[1] for pair in successful_cases]
        per_repeat.append({
            "repeat": index + 1,
            "successful_cases": len(successful_cases),
            "failed_cases": len(cases) - len(successful_cases),
            "baseline_metrics_same_subset": grade_predictions(
                expected,
                [baseline_classify(
                    case.get("synthetic_text", "") if case.get("source_type") in ("synthetic", "held_out_synthetic")
                    else texts.get(case.get("response_id"), "")
                ) for case in cases if case_runs[case["case_id"]][index]["status"] == "success"]
            ),
            "provider_metrics": grade_predictions(expected, predicted),
        })

    stability = {}
    for case_id, runs in case_runs.items():
        predictions = [r["prediction"] for r in runs if r["prediction"] is not None]
        successful_count = len(predictions)
        distinct = {json.dumps(p, sort_keys=True) for p in predictions}
        stability[case_id] = {
            "successful_runs": successful_count,
            "failed_runs": repeats - successful_count,
            "stable_across_successful_runs": (
                len(distinct) == 1 if successful_count >= 2 else None
            ),
            "distinct_prediction_count": len(distinct),
            "runs": runs,
        }
    stable_eligible = [
        item for item in stability.values()
        if item["successful_runs"] >= 2
    ]
    stable_count = sum(
        item["stable_across_successful_runs"] is True
        for item in stable_eligible
    )
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "study": "real_model_repeatability",
        "split": split,
        "case_file": cases_path,
        "repeats_per_case": repeats,
        "execution_metadata": {
            "provider": classifier.provider,
            "model": classifier.model,
            "classifier_version": classifier.classifier_version,
        },
        "counts": {
            "cases": len(cases),
            "total_calls": len(all_calls),
            "successful_calls": len(successful),
            "failed_calls": len(failed),
            "call_coverage": round(len(successful) / len(all_calls), 4) if all_calls else 0,
            "cases_with_at_least_two_successes": len(stable_eligible),
            "stable_cases": stable_count,
            "stability_rate_among_repeatable_cases": (
                round(stable_count / len(stable_eligible), 4) if stable_eligible else None
            ),
        },
        "latency_seconds": {
            "mean": round(statistics.mean(latencies), 4) if latencies else None,
            "median": round(statistics.median(latencies), 4) if latencies else None,
            "p95": round(sorted(latencies)[min(len(latencies)-1, int(0.95 * len(latencies)))], 4) if latencies else None,
        },
        "per_repeat_metrics": per_repeat,
        "per_case": stability,
        "limitations": [
            "Repeated calls measure provider output stability under the same saved inputs and current configuration; they do not establish generalization.",
            "A case is counted as stable only when at least two calls succeeded and every successful prediction matched exactly.",
            "Latency includes client-side request time and excludes external billing reconciliation.",
            "Baseline and provider metrics are paired on the same successful cases within each repeat.",
        ],
    }
    destination = Path(output_path or f"evaluation/results/repeatability_{split}.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(destination), "counts": result["counts"], "latency_seconds": result["latency_seconds"]}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure real-model repeatability on a frozen evaluation split.")
    parser.add_argument("--split", choices=("regression", "held_out"), default="regression")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cases-path")
    parser.add_argument("--output")
    args = parser.parse_args()
    run_repeatability(
        split=args.split,
        repeats=args.repeats,
        cases_path=args.cases_path,
        output_path=args.output,
    )
