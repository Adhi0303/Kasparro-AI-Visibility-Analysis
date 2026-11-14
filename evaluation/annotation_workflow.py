"""Blinded double-annotation and adjudication workflow for held-out cases.

This module creates reviewer packets without reference labels or model predictions,
then reconciles two independent submissions while preserving an audit trail.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

LABELS = (
    "kasparro_mentioned",
    "kasparro_recommended",
    "kasparro_negative",
)
ANNOTATION_STATUS = "independently_double_annotated_and_adjudicated"
_ANNOTATOR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: each JSONL record must be an object")
            rows.append(row)
    return rows


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _validate_annotator_id(value: Any, field: str = "annotator_id") -> str:
    if not isinstance(value, str) or not _ANNOTATOR_ID.fullmatch(value):
        raise ValueError(
            f"{field} must be 1-64 characters using letters, digits, dot, underscore or hyphen"
        )
    return value


def _validate_labels(value: Any, context: str) -> dict[str, bool]:
    if not isinstance(value, dict) or set(value) != set(LABELS):
        raise ValueError(f"{context}: labels must contain exactly {', '.join(LABELS)}")
    if any(type(value[label]) is not bool for label in LABELS):
        raise ValueError(f"{context}: every label must be a JSON boolean")
    if value["kasparro_recommended"] and not value["kasparro_mentioned"]:
        raise ValueError(f"{context}: recommendation cannot be true when mention is false")
    if value["kasparro_negative"] and not value["kasparro_mentioned"]:
        raise ValueError(f"{context}: negative cannot be true when mention is false")
    return {label: value[label] for label in LABELS}


def _unique_cases(cases: list[dict[str, Any]], context: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in cases:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{context}: each case requires a non-empty case_id")
        if case_id in indexed:
            raise ValueError(f"{context}: duplicate case_id {case_id}")
        indexed[case_id] = row
    return indexed


def export_annotation_templates(
    cases_path: str | Path = "evaluation/held_out_cases.jsonl",
    output_dir: str | Path = "evaluation/annotations",
    reviewer_ids: tuple[str, str] = ("reviewer_a", "reviewer_b"),
    seed: int = 2026,
) -> list[str]:
    """Write separately shuffled annotation templates with no gold labels."""
    if len(reviewer_ids) != 2:
        raise ValueError("Exactly two reviewer IDs are required")
    reviewer_a, reviewer_b = (
        _validate_annotator_id(reviewer_ids[0]),
        _validate_annotator_id(reviewer_ids[1]),
    )
    if reviewer_a == reviewer_b:
        raise ValueError("The two reviewers must have distinct IDs")

    cases = _read_jsonl(cases_path)
    indexed = _unique_cases(cases, "source cases")
    if not indexed:
        raise ValueError("The held-out case file is empty")

    templates: list[str] = []
    for reviewer_index, reviewer_id in enumerate((reviewer_a, reviewer_b)):
        packet = []
        for case in cases:
            source_type = case.get("source_type")
            if source_type not in ("synthetic", "held_out_synthetic"):
                raise ValueError(
                    f"{case['case_id']}: blinded packets currently require synthetic source text"
                )
            response_text = case.get("synthetic_text")
            prompt_text = case.get("prompt_text", "")
            if not isinstance(response_text, str) or not response_text.strip():
                raise ValueError(f"{case['case_id']}: missing synthetic_text")
            if not isinstance(prompt_text, str):
                raise ValueError(f"{case['case_id']}: prompt_text must be a string")

            packet.append({
                "schema_version": "1.0",
                "annotator_id": reviewer_id,
                "case_id": case["case_id"],
                "engine": case.get("engine", "unknown"),
                "prompt_text": prompt_text,
                "response_text": response_text,
                "labels": {label: None for label in LABELS},
                "rationale": "",
            })

        random.Random(seed + reviewer_index).shuffle(packet)
        output_path = Path(output_dir) / f"{reviewer_id}.jsonl"
        _write_jsonl(output_path, packet)
        templates.append(str(output_path))
    return templates


def _load_reviewer_submission(
    path: str | Path,
    expected_case_ids: set[str],
) -> tuple[str, dict[str, dict[str, bool]]]:
    rows = _read_jsonl(path)
    if not rows:
        raise ValueError(f"{path}: reviewer submission is empty")

    reviewer_ids = {
        _validate_annotator_id(row.get("annotator_id"), f"{path}:annotator_id")
        for row in rows
    }
    if len(reviewer_ids) != 1:
        raise ValueError(f"{path}: all records must use the same annotator_id")

    indexed = _unique_cases(rows, str(path))
    received = set(indexed)
    if received != expected_case_ids:
        missing = sorted(expected_case_ids - received)
        extra = sorted(received - expected_case_ids)
        raise ValueError(
            f"{path}: case coverage mismatch; missing={missing[:5]}, extra={extra[:5]}"
        )

    annotations: dict[str, dict[str, bool]] = {}
    forbidden = {"expected", "proposed", "baseline", "prediction", "score", "confidence"}
    for case_id, row in indexed.items():
        leaked_fields = forbidden.intersection(key.lower() for key in row)
        if leaked_fields:
            raise ValueError(
                f"{path}:{case_id}: reviewer packet must not contain model/gold fields: "
                f"{sorted(leaked_fields)}"
            )
        annotations[case_id] = _validate_labels(row.get("labels"), f"{path}:{case_id}")
    return next(iter(reviewer_ids)), annotations


def _cohen_kappa(first: list[bool], second: list[bool]) -> float | None:
    if len(first) != len(second):
        raise ValueError("Annotation arrays must have equal length")
    if not first:
        return None
    observed = sum(a is b for a, b in zip(first, second)) / len(first)
    first_true = sum(first) / len(first)
    second_true = sum(second) / len(second)
    expected = first_true * second_true + (1 - first_true) * (1 - second_true)
    if expected == 1:
        return None
    return round((observed - expected) / (1 - expected), 4)


def finalize_annotations(
    reviewer_a_path: str | Path,
    reviewer_b_path: str | Path,
    cases_path: str | Path = "evaluation/held_out_cases.jsonl",
    adjudication_path: str | Path | None = None,
    output_path: str | Path = "evaluation/held_out_adjudicated_cases.jsonl",
    summary_path: str | Path = "evaluation/annotations/agreement_summary.json",
    adjudication_template_path: str | Path = "evaluation/annotations/adjudication_required.jsonl",
) -> dict[str, Any]:
    """Reconcile two blinded submissions; require a third decision per disagreement."""
    source_rows = _read_jsonl(cases_path)
    source = _unique_cases(source_rows, "source cases")
    expected_ids = set(source)

    reviewer_a_id, reviewer_a = _load_reviewer_submission(reviewer_a_path, expected_ids)
    reviewer_b_id, reviewer_b = _load_reviewer_submission(reviewer_b_path, expected_ids)
    if reviewer_a_id == reviewer_b_id:
        raise ValueError("Independent submissions must have distinct reviewer IDs")

    disagreements = {
        case_id for case_id in expected_ids
        if any(reviewer_a[case_id][label] != reviewer_b[case_id][label] for label in LABELS)
    }

    adjudications: dict[str, tuple[str, dict[str, bool], str]] = {}
    if adjudication_path is not None and Path(adjudication_path).exists():
        rows = _read_jsonl(adjudication_path)
        indexed = _unique_cases(rows, "adjudication file")
        if set(indexed) != disagreements:
            missing = sorted(disagreements - set(indexed))
            extra = sorted(set(indexed) - disagreements)
            raise ValueError(
                f"Adjudication coverage mismatch; missing={missing[:5]}, extra={extra[:5]}"
            )
        for case_id, row in indexed.items():
            adjudicator_id = _validate_annotator_id(
                row.get("adjudicator_id"), f"adjudication:{case_id}:adjudicator_id"
            )
            if adjudicator_id in (reviewer_a_id, reviewer_b_id):
                raise ValueError(f"{case_id}: adjudicator must be a third independent reviewer")
            rationale = row.get("rationale")
            if not isinstance(rationale, str) or len(rationale.strip()) < 8:
                raise ValueError(f"{case_id}: adjudication rationale must be at least 8 characters")
            labels = _validate_labels(row.get("labels"), f"adjudication:{case_id}")
            adjudications[case_id] = (adjudicator_id, labels, rationale.strip())

    unresolved = disagreements - set(adjudications)
    if unresolved:
        template = []
        for case_id in sorted(unresolved):
            template.append({
                "case_id": case_id,
                "reviewer_a": {"annotator_id": reviewer_a_id, "labels": reviewer_a[case_id]},
                "reviewer_b": {"annotator_id": reviewer_b_id, "labels": reviewer_b[case_id]},
                "adjudicator_id": "",
                "labels": {label: None for label in LABELS},
                "rationale": "",
            })
        _write_jsonl(adjudication_template_path, template)
        raise ValueError(
            f"{len(unresolved)} cases require third-reviewer adjudication. "
            f"Fill {adjudication_template_path} and rerun finalize."
        )

    output_rows: list[dict[str, Any]] = []
    for case_id in sorted(expected_ids):
        row = dict(source[case_id])
        first = reviewer_a[case_id]
        second = reviewer_b[case_id]
        if case_id in adjudications:
            adjudicator_id, final_labels, rationale = adjudications[case_id]
            adjudicator_record: dict[str, Any] | None = {
                "annotator_id": adjudicator_id,
                "labels": final_labels,
                "rationale": rationale,
            }
        else:
            final_labels = first
            adjudicator_record = None

        row["provisional_expected"] = row.get("expected")
        row["expected"] = final_labels
        row["annotation_status"] = ANNOTATION_STATUS
        row["annotation_audit"] = {
            "reviewer_a": {"annotator_id": reviewer_a_id, "labels": first},
            "reviewer_b": {"annotator_id": reviewer_b_id, "labels": second},
            "reviewers_agreed": case_id not in disagreements,
            "adjudication": adjudicator_record,
        }
        output_rows.append(row)

    _write_jsonl(output_path, output_rows)

    per_label = {}
    for label in LABELS:
        first_values = [reviewer_a[cid][label] for cid in sorted(expected_ids)]
        second_values = [reviewer_b[cid][label] for cid in sorted(expected_ids)]
        agreement = sum(a is b for a, b in zip(first_values, second_values))
        per_label[label] = {
            "raw_agreement": round(agreement / len(expected_ids), 4) if expected_ids else None,
            "cohen_kappa": _cohen_kappa(first_values, second_values),
            "support": len(expected_ids),
        }

    summary = {
        "annotation_status": ANNOTATION_STATUS,
        "total_cases": len(expected_ids),
        "reviewer_ids": [reviewer_a_id, reviewer_b_id],
        "unanimous_cases": len(expected_ids) - len(disagreements),
        "disputed_cases": len(disagreements),
        "adjudicated_cases": len(adjudications),
        "overall_raw_agreement": round(
            sum(
                all(reviewer_a[cid][label] == reviewer_b[cid][label] for label in LABELS)
                for cid in expected_ids
            ) / len(expected_ids), 4
        ) if expected_ids else None,
        "per_label_agreement": per_label,
        "output_path": str(output_path),
        "note": "Reviewer agreement is measured before adjudication; adjudicated labels are retained with a per-case audit trail.",
    }
    target = Path(summary_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and reconcile blinded held-out annotations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Create two separately shuffled, label-blinded reviewer packets.")
    export_parser.add_argument("--cases", default="evaluation/held_out_cases.jsonl")
    export_parser.add_argument("--output-dir", default="evaluation/annotations")
    export_parser.add_argument("--reviewer-a", default="reviewer_a")
    export_parser.add_argument("--reviewer-b", default="reviewer_b")
    export_parser.add_argument("--seed", type=int, default=2026)

    finalize_parser = subparsers.add_parser("finalize", help="Validate submissions and reconcile/adjudicate labels.")
    finalize_parser.add_argument("--cases", default="evaluation/held_out_cases.jsonl")
    finalize_parser.add_argument("--reviewer-a", required=True)
    finalize_parser.add_argument("--reviewer-b", required=True)
    finalize_parser.add_argument("--adjudication")
    finalize_parser.add_argument("--output", default="evaluation/held_out_adjudicated_cases.jsonl")
    finalize_parser.add_argument("--summary", default="evaluation/annotations/agreement_summary.json")
    finalize_parser.add_argument("--adjudication-template", default="evaluation/annotations/adjudication_required.jsonl")

    args = parser.parse_args()
    if args.command == "export":
        for path in export_annotation_templates(
            cases_path=args.cases,
            output_dir=args.output_dir,
            reviewer_ids=(args.reviewer_a, args.reviewer_b),
            seed=args.seed,
        ):
            print(path)
    else:
        summary = finalize_annotations(
            reviewer_a_path=args.reviewer_a,
            reviewer_b_path=args.reviewer_b,
            cases_path=args.cases,
            adjudication_path=args.adjudication,
            output_path=args.output,
            summary_path=args.summary,
            adjudication_template_path=args.adjudication_template,
        )
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
