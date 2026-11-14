import argparse
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from evaluation.grader import grade_predictions, baseline_classify
from app.evidence import find_evidence_match
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


def load_response_prompt_texts(responses_path: str = "data/responses.jsonl") -> Dict[str, str]:
    prompts_by_id: Dict[str, str] = {}
    prompts_file = os.path.join(os.path.dirname(responses_path), "prompts.jsonl")
    if os.path.exists(prompts_file):
        with open(prompts_file, "r", encoding="utf-8") as pf:
            for line in pf:
                line = line.strip()
                if line:
                    p = json.loads(line)
                    prompts_by_id[p["prompt_id"]] = p.get("text", "")

    resp_prompts: Dict[str, str] = {}
    if os.path.exists(responses_path):
        with open(responses_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    resp_prompts[item["response_id"]] = prompts_by_id.get(item.get("prompt_id", ""), "")
    return resp_prompts


def run_evaluation(
    execution_mode: str = "replay",
    cases_path: Optional[str] = None,
    responses_path: str = "data/responses.jsonl",
    output_dir: str = "evaluation/results",
    settings_override: Optional[Settings] = None,
    split: str = "regression",
) -> Dict[str, Any]:
    if execution_mode not in ("replay", "real_model"):
        raise ValueError(f"Invalid execution_mode '{execution_mode}'. Expected 'replay' or 'real_model'.")

    if split not in ("regression", "held_out", "all"):
        raise ValueError("split must be one of: regression, held_out, all")
    if cases_path is None:
        if split == "regression":
            cases_path = "evaluation/cases.jsonl"
        elif split == "held_out":
            cases_path = "evaluation/held_out_cases.jsonl"
        else:
            raise ValueError("The all split requires an explicit combined cases_path; do not concatenate development and held-out sets for model selection.")
    cases = load_cases(cases_path)
    if split == "held_out":
        regression_cases = load_cases("evaluation/cases.jsonl")
        regression_prompts = {case.get("prompt_id") for case in regression_cases}
        held_out_prompts = {case.get("prompt_id") for case in cases}
        overlap = regression_prompts.intersection(held_out_prompts)
        if overlap:
            raise ValueError(f"Held-out prompt families overlap regression split: {sorted(overlap)[:5]}")
        non_held_out = [
            case.get("case_id") for case in cases
            if case.get("source_type") != "held_out_synthetic"
        ]
        if non_held_out:
            raise ValueError(
                "The held_out split may contain only held_out_synthetic cases; "
                f"invalid cases: {non_held_out[:5]}"
            )
    case_ids = [case.get("case_id") for case in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids) or len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case IDs must be non-empty and unique")
    response_texts = load_response_texts(responses_path)
    response_prompts = load_response_prompt_texts(responses_path)
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

    expected_all_cases: List[Dict[str, bool]] = []
    baseline_all_cases: List[Dict[str, bool]] = []
    expected_completed: List[Dict[str, bool]] = []
    baseline_completed: List[Dict[str, bool]] = []
    proposed_completed: List[Dict[str, bool]] = []
    failed_cases: List[Dict[str, Any]] = []
    case_details: List[Dict[str, Any]] = []

    import inspect
    classify_sig = inspect.signature(classifier.classify)
    accepts_prompt_text = "prompt_text" in classify_sig.parameters or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in classify_sig.parameters.values()
    )

    for c in cases:
        c_id = c["case_id"]
        source_type = c.get("source_type", "supplied")
        resp_id = c.get("response_id")
        is_synthetic = source_type in ("synthetic", "held_out_synthetic")
        text = c.get("synthetic_text", "") if is_synthetic else response_texts.get(resp_id, "")
        prompt_text = c.get("prompt_text") if is_synthetic else response_prompts.get(resp_id)
        expected = c["expected"]

        b_pred = baseline_classify(text)
        expected_all_cases.append(expected)
        baseline_all_cases.append(b_pred)
        classify_kwargs = {
            "response_id": resp_id or c_id,
            "engine": c.get("engine", "unknown"),
            "answer_text": text,
        }
        if accepts_prompt_text:
            classify_kwargs["prompt_text"] = prompt_text or None
        res = classifier.classify(**classify_kwargs)

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

        validated_ev = []
        rejected_ev = []
        for ev in res.evidence:
            match = find_evidence_match(ev.excerpt, text, location=ev.location)
            if match["valid"]:
                validated_ev.append({
                    "excerpt": match["canonical_excerpt"],
                    "location": ev.location,
                    "start_offset": match["start_offset"],
                    "end_offset": match["end_offset"],
                    "match_type": match["match_type"],
                })
            else:
                rejected_ev.append({
                    "excerpt": ev.excerpt,
                    "location": ev.location,
                    "rejection_reason": match["rejection_reason"],
                })

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
            "evidence_validation": {
                "accepted_count": len(validated_ev),
                "rejected_count": len(rejected_ev),
            },
            "notes": c.get("notes", ""),
        })

    # Keep the baseline/proposed comparison on the same successful subset.
    # Also retain a full-cohort baseline and penalize failed classifier calls in
    # the operational, coverage-adjusted exact-match measure.
    baseline_metrics = grade_predictions(expected_completed, baseline_completed)
    baseline_all_metrics = grade_predictions(expected_all_cases, baseline_all_cases)
    proposed_metrics = grade_predictions(expected_completed, proposed_completed)
    total_case_count = len(cases)
    successful_case_count = len(expected_completed)
    coverage_rate = successful_case_count / total_case_count if total_case_count else 0.0
    coverage_adjusted_agreement = (
        proposed_metrics["exact_matches"] / total_case_count if total_case_count else 0.0
    )

    if split == "held_out":
        annotation_statuses = {case.get("annotation_status") for case in cases}
        annotation_status = (
            "independently_double_annotated_and_adjudicated"
            if annotation_statuses == {"independently_double_annotated_and_adjudicated"}
            else "provisional_single_annotator"
        )
        annotation_note = (
            "Held-out labels were independently double-annotated and disagreements were adjudicated."
            if annotation_status == "independently_double_annotated_and_adjudicated"
            else "Held-out labels are provisional single-annotator labels and are not independently adjudicated."
        )
    else:
        annotation_status = "regression_reference_labels"
        annotation_note = "Regression labels are development references, not an independent held-out benchmark."

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    supplied_count = len([c for c in cases if c.get("source_type") == "supplied"])
    synthetic_count = len([c for c in cases if c.get("source_type") in ("synthetic", "held_out_synthetic")])
    held_out_count = len([c for c in cases if c.get("source_type") == "held_out_synthetic"])

    split_suffix = "_held_out" if split == "held_out" else ""
    if execution_mode == "real_model":
        md_filename = f"eval_provider_report{split_suffix}.md"
        json_filename = "eval_provider_held_out_results.json" if split == "held_out" else "eval_provider_results.json"
        title = "# Provider Evaluation Report (Real-Model Execution)"
        mode_desc = (
            f"real_model (provider={exec_meta['provider']}, model={exec_meta['model']}, "
            f"classifier_version={exec_meta['classifier_version']})"
        )
    else:
        md_filename = f"eval_comparison_report{split_suffix}.md"
        json_filename = "eval_held_out_results.json" if split == "held_out" else "eval_results.json"
        title = "# Evaluation and Grader Comparison Report"
        mode_desc = f"replay (keyless deterministic contextual classifier, version={exec_meta['classifier_version']})"

    agreement_delta = (proposed_metrics["agreement_rate"] - baseline_metrics["agreement_rate"]) * 100
    sign = "+" if agreement_delta >= 0 else ""

    md_content = f"""{title}

- **Generated:** {timestamp}
- **Pack Version:** 1.0.0
- **Evaluation Split:** {split}\n- **Total Cases:** {len(cases)} ({supplied_count} supplied, {synthetic_count} synthetic; {held_out_count} held-out synthetic)
- **Successful Evaluations:** {len(expected_completed)}
- **Failed/Skipped Evaluations:** {len(failed_cases)}
- **Execution Mode:** {mode_desc}
- **Annotation Status:** {annotation_status}

---

## 1. Executive Summary

This evaluation compares the **{execution_mode}** classifier (`{exec_meta['model']}`) with a **Naive Rule-Based Baseline** on the {len(expected_completed)} cases where classifier execution succeeded. It does not describe provisional labels as independently validated ground truth.

## 2. Execution Coverage

- **Total cases:** {total_case_count}
- **Successful classifier calls:** {successful_case_count}
- **Failed/skipped classifier calls:** {len(failed_cases)}
- **Execution coverage:** {coverage_rate * 100:.1f}%
- **Coverage-adjusted exact-match agreement:** {coverage_adjusted_agreement * 100:.1f}% ({proposed_metrics['exact_matches']}/{total_case_count})

Classification metrics and the baseline comparison below use the matched successful subset. Coverage-adjusted agreement uses the full cohort, treating failed classifier calls as unmatched rather than silently excluding them.

| Metric | Rule-Based Baseline | Evaluated Classifier | Delta |
|---|---|---|---|
| **Exact-Match Agreement** | {baseline_metrics['agreement_rate'] * 100:.1f}% ({baseline_metrics['exact_matches']}/{len(expected_completed)}) | {proposed_metrics['agreement_rate'] * 100:.1f}% ({proposed_metrics['exact_matches']}/{len(expected_completed)}) | {sign}{agreement_delta:.1f}% |
| **Mention Precision** | {baseline_metrics['per_label']['kasparro_mentioned']['precision']} | {proposed_metrics['per_label']['kasparro_mentioned']['precision']} | Context-aware prompt echo filtering |
| **Mention Recall** | {baseline_metrics['per_label']['kasparro_mentioned']['recall']} | {proposed_metrics['per_label']['kasparro_mentioned']['recall']} | Genuine brand discussion retained |
| **Recommendation F1** | {baseline_metrics['per_label']['kasparro_recommended']['f1']} | {proposed_metrics['per_label']['kasparro_recommended']['f1']} | Target-aware recommendation attribution |
| **Negative F1** | {baseline_metrics['per_label']['kasparro_negative']['f1']} | {proposed_metrics['per_label']['kasparro_negative']['f1']} | Target-aware sentiment & neutrality handling |

---

## 3. Per-Label Breakdown

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

## 4. Failure, Diagnosis, Fix, and Regression

As required by Section 16 of the assignment brief, actual failures observed during implementation are documented in `DECISION_NOTE.md` and verified via regression tests in `tests/test_analysis.py` (`test_all_diagnostic_evidence_verbatim_integrity` and contextual target-attribution tests).

---

## 5. Evaluation Cases Detail

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
            "held_out_cases": held_out_count,
            "split": split,
            "annotation_status": annotation_status,
            "annotation_note": annotation_note,
            "evaluated_cases": len(expected_completed),
            "failed_cases": len(failed_cases),
        },
        "baseline_metrics": baseline_metrics,
        "baseline_metrics_all_cases": baseline_all_metrics,
        "proposed_metrics": proposed_metrics,
        "coverage_metrics": {
            "total_cases": total_case_count,
            "successful_classifier_calls": successful_case_count,
            "failed_classifier_calls": len(failed_cases),
            "coverage_rate": round(coverage_rate, 4),
            "coverage_adjusted_exact_match_rate": round(coverage_adjusted_agreement, 4),
            "exact_matches_on_successful_calls": proposed_metrics["exact_matches"],
        },
        "failures": failed_cases,
        "cases": case_details,
    }

    json_path = os.path.join(output_dir, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(eval_json, indent=2))

    print(f"Evaluation completed ({execution_mode})! Report written to {md_path}")
    print(
        f"Matched-subset agreement ({successful_case_count}/{total_case_count} successful) - "
        f"Baseline: {baseline_metrics['agreement_rate'] * 100:.1f}%, "
        f"Evaluated: {proposed_metrics['agreement_rate'] * 100:.1f}%"
    )
    print(
        f"Execution coverage: {coverage_rate * 100:.1f}%; "
        f"coverage-adjusted exact-match agreement: {coverage_adjusted_agreement * 100:.1f}%"
    )
    if failed_cases:
        print(f"Explicit failures recorded: {len(failed_cases)} (first reason: {failed_cases[0]['failure_reason']})")
    return eval_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Kasparro classifier evaluation.")
    parser.add_argument("--split", choices=["regression", "held_out"], default="regression", help="Use the regression set for development or the isolated held-out set for final evaluation.")
    parser.add_argument(
        "--mode",
        choices=["replay", "real_model"],
        default="replay",
        help="Execution mode: deterministic 'replay' (default) or live/configured 'real_model'.",
    )
    parser.add_argument(
        "--cases-path",
        help="Optional alternate JSONL cases file (for example, independently adjudicated held-out labels).",
    )
    args = parser.parse_args()
    run_evaluation(execution_mode=args.mode, split=args.split, cases_path=args.cases_path)
