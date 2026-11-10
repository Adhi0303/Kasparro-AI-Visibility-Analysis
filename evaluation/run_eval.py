import argparse
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from evaluation.grader import grade_predictions, baseline_classify
from app.llm.replay import ReplayClassifier
from app.llm.provider import ProviderClassifier, DEFAULT_LLM_BASE_URL
from app.config import get_settings, Settings


def load_cases(cases_path: str = "evaluation/cases.jsonl") -> List[Dict[str, Any]]:
    cases = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def load_response_texts(responses_path: str = "data/responses.jsonl") -> Dict[str, str]:
    texts = {}
    if os.path.exists(responses_path):
        with open(responses_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    texts[item["response_id"]] = item.get("answer_text", "")
    return texts


def run_evaluation(
    execution_mode: str = "replay",
    cases_path: str = "evaluation/cases.jsonl",
    responses_path: str = "data/responses.jsonl",
    output_dir: str = "evaluation/results",
    settings_override: Optional[Settings] = None,
) -> Dict[str, Any]:
    if execution_mode not in ("replay", "real_model"):
        raise ValueError(f"Invalid execution_mode '{execution_mode}'. Expected 'replay' or 'real_model'.")

    cases = load_cases(cases_path)
    response_texts = load_response_texts(responses_path)
    settings = settings_override or get_settings()

    if execution_mode == "real_model":
        classifier = ProviderClassifier(settings)
        exec_meta = {
            "execution_mode": "real_model",
            "provider": classifier.provider,
            "model": classifier.model,
            "base_url": classifier.base_url or DEFAULT_LLM_BASE_URL,
            "classifier_version": classifier.classifier_version,
        }
    else:
        classifier = ReplayClassifier()
        exec_meta = {
            "execution_mode": "replay",
            "provider": "deterministic_replay",
            "model": "contextual-rules-v1",
            "base_url": None,
            "classifier_version": classifier.classifier_version,
        }

    expected_completed: List[Dict[str, bool]] = []
    baseline_completed: List[Dict[str, bool]] = []
    proposed_completed: List[Dict[str, bool]] = []
    failed_cases: List[Dict[str, Any]] = []
    case_details: List[Dict[str, Any]] = []

    for c in cases:
        c_id = c["case_id"]
        source_type = c.get("source_type", "supplied")
        resp_id = c.get("response_id")
        text = c.get("synthetic_text", "") if source_type == "synthetic" else response_texts.get(resp_id, "")
        expected = c["expected"]

        b_pred = baseline_classify(text)
        res = classifier.classify(
            response_id=resp_id or c_id,
            engine=c.get("engine", "unknown"),
            answer_text=text,
        )

        if res.status != "success":
            failed_cases.append({
                "case_id": c_id,
                "status": res.status,
                "failure_reason": res.failure_reason,
            })
            case_details.append({
                "case_id": c_id,
                "source_type": source_type,
                "response_id": resp_id,
                "status": res.status,
                "failure_reason": res.failure_reason,
                "expected": expected,
                "baseline": b_pred,
                "proposed": None,
                "notes": c.get("notes", ""),
            })
            continue

        p_pred = {
            "kasparro_mentioned": res.kasparro_mentioned,
            "kasparro_recommended": res.kasparro_recommended,
            "kasparro_negative": res.kasparro_negative,
        }
        expected_completed.append(expected)
        baseline_completed.append(b_pred)
        proposed_completed.append(p_pred)

        case_details.append({
            "case_id": c_id,
            "source_type": source_type,
            "response_id": resp_id,
            "status": res.status,
            "expected": expected,
            "baseline": b_pred,
            "proposed": p_pred,
            "notes": c.get("notes", ""),
        })

    baseline_metrics = grade_predictions(expected_completed, baseline_completed)
    proposed_metrics = grade_predictions(expected_completed, proposed_completed)

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    supplied_count = len([c for c in cases if c.get("source_type") == "supplied"])
    synthetic_count = len([c for c in cases if c.get("source_type") == "synthetic"])

    if execution_mode == "real_model":
        md_filename = "eval_provider_report.md"
        json_filename = "eval_provider_results.json"
        title = "# Provider Evaluation Report (Real-Model Execution)"
        mode_desc = (
            f"real_model (provider={exec_meta['provider']}, model={exec_meta['model']}, "
            f"classifier_version={exec_meta['classifier_version']})"
        )
    else:
        md_filename = "eval_comparison_report.md"
        json_filename = "eval_results.json"
        title = "# Evaluation and Grader Comparison Report"
        mode_desc = f"replay (keyless deterministic contextual classifier, version={exec_meta['classifier_version']})"

    agreement_delta = (proposed_metrics["agreement_rate"] - baseline_metrics["agreement_rate"]) * 100
    sign = "+" if agreement_delta >= 0 else ""

    md_content = f"""{title}

- **Generated:** {timestamp}
- **Pack Version:** 1.0.0
- **Total Cases:** {len(cases)} ({supplied_count} supplied, {synthetic_count} synthetic)
- **Successful Evaluations:** {len(expected_completed)}
- **Failed/Skipped Evaluations:** {len(failed_cases)}
- **Execution Mode:** {mode_desc}

---

## 1. Executive Summary

This evaluation benchmarks the **{execution_mode}** classifier (`{exec_meta['model']}`) against a **Naive Rule-Based Baseline** across {len(expected_completed)} successfully evaluated gold-standard cases.

| Metric | Rule-Based Baseline | Evaluated Classifier | Delta |
|---|---|---|---|
| **Exact-Match Agreement** | {baseline_metrics['agreement_rate'] * 100:.1f}% ({baseline_metrics['exact_matches']}/{len(expected_completed)}) | {proposed_metrics['agreement_rate'] * 100:.1f}% ({proposed_metrics['exact_matches']}/{len(expected_completed)}) | {sign}{agreement_delta:.1f}% |
| **Mention Precision** | {baseline_metrics['per_label']['kasparro_mentioned']['precision']} | {proposed_metrics['per_label']['kasparro_mentioned']['precision']} | Context-aware prompt echo filtering |
| **Mention Recall** | {baseline_metrics['per_label']['kasparro_mentioned']['recall']} | {proposed_metrics['per_label']['kasparro_mentioned']['recall']} | Genuine brand discussion retained |
| **Recommendation F1** | {baseline_metrics['per_label']['kasparro_recommended']['f1']} | {proposed_metrics['per_label']['kasparro_recommended']['f1']} | Target-aware recommendation attribution |
| **Negative F1** | {baseline_metrics['per_label']['kasparro_negative']['f1']} | {proposed_metrics['per_label']['kasparro_negative']['f1']} | Target-aware sentiment & neutrality handling |

---

## 2. Per-Label Breakdown

### Mention Detection (`kasparro_mentioned`)
- **Baseline:** Precision: {baseline_metrics['per_label']['kasparro_mentioned']['precision']}, Recall: {baseline_metrics['per_label']['kasparro_mentioned']['recall']}
- **Evaluated ({execution_mode}):** Precision: {proposed_metrics['per_label']['kasparro_mentioned']['precision']}, Recall: {proposed_metrics['per_label']['kasparro_mentioned']['recall']}

### Recommendation Detection (`kasparro_recommended`)
- **Baseline:** Precision: {baseline_metrics['per_label']['kasparro_recommended']['precision']}, Recall: {baseline_metrics['per_label']['kasparro_recommended']['recall']}
- **Evaluated ({execution_mode}):** Precision: {proposed_metrics['per_label']['kasparro_recommended']['precision']}, Recall: {proposed_metrics['per_label']['kasparro_recommended']['recall']}

### Negative Characterization (`kasparro_negative`)
- **Baseline:** Precision: {baseline_metrics['per_label']['kasparro_negative']['precision']}, Recall: {baseline_metrics['per_label']['kasparro_negative']['recall']}
- **Evaluated ({execution_mode}):** Precision: {proposed_metrics['per_label']['kasparro_negative']['precision']}, Recall: {proposed_metrics['per_label']['kasparro_negative']['recall']}

---

## 3. Failure, Diagnosis, Fix, and Regression

As required by Section 16 of the assignment brief, actual failures observed during implementation are documented in `DECISION_NOTE.md` and verified via regression tests in `tests/test_analysis.py` (`test_all_diagnostic_evidence_verbatim_integrity` and contextual target-attribution tests).

---

## 4. Evaluation Cases Detail

```json
{json.dumps(case_details, indent=2)}
```
"""

    md_path = os.path.join(output_dir, md_filename)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    eval_json = {
        "timestamp": timestamp,
        "execution_metadata": exec_meta,
        "counts": {
            "total_cases": len(cases),
            "supplied_cases": supplied_count,
            "synthetic_cases": synthetic_count,
            "evaluated_cases": len(expected_completed),
            "failed_cases": len(failed_cases),
        },
        "baseline_metrics": baseline_metrics,
        "proposed_metrics": proposed_metrics,
        "failures": failed_cases,
        "cases": case_details,
    }

    json_path = os.path.join(output_dir, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(eval_json, indent=2))

    print(f"Evaluation completed ({execution_mode})! Report written to {md_path}")
    print(
        f"Agreement rate ({len(expected_completed)}/{len(cases)} evaluated) - "
        f"Baseline: {baseline_metrics['agreement_rate'] * 100:.1f}%, "
        f"Evaluated: {proposed_metrics['agreement_rate'] * 100:.1f}%"
    )
    if failed_cases:
        print(f"Explicit failures recorded: {len(failed_cases)} (first reason: {failed_cases[0]['failure_reason']})")
    return eval_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Kasparro classifier evaluation.")
    parser.add_argument(
        "--mode",
        choices=["replay", "real_model"],
        default="replay",
        help="Execution mode: deterministic 'replay' (default) or live/configured 'real_model'.",
    )
    args = parser.parse_args()
    run_evaluation(execution_mode=args.mode)
