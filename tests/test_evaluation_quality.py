import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _case(case_id: str, prompt_id: str, expected: dict) -> dict:
    return {
        "case_id": case_id,
        "source_type": "held_out_synthetic",
        "response_id": f"response-{case_id}",
        "engine": "chatgpt",
        "prompt_id": prompt_id,
        "prompt_text": "Should I consider Kasparro?",
        "synthetic_text": "Kasparro is worth considering for B2B SaaS teams.",
        "expected": expected,
        "annotation_status": "provisional_single_annotator",
        "notes": "private provisional label note",
    }


def test_blinded_annotation_packets_hide_reference_labels_and_model_fields(tmp_path):
    from evaluation.annotation_workflow import export_annotation_templates

    cases_path = tmp_path / "cases.jsonl"
    _write_jsonl(cases_path, [
        _case("case-1", "family-1", {
            "kasparro_mentioned": True,
            "kasparro_recommended": True,
            "kasparro_negative": False,
        }),
        _case("case-2", "family-2", {
            "kasparro_mentioned": True,
            "kasparro_recommended": False,
            "kasparro_negative": False,
        }),
    ])

    outputs = export_annotation_templates(
        cases_path=cases_path,
        output_dir=tmp_path / "packets",
        reviewer_ids=("reviewer_a", "reviewer_b"),
        seed=17,
    )
    assert len(outputs) == 2

    for output in outputs:
        rows = _read_jsonl(Path(output))
        assert {row["case_id"] for row in rows} == {"case-1", "case-2"}
        for row in rows:
            assert row["labels"] == {
                "kasparro_mentioned": None,
                "kasparro_recommended": None,
                "kasparro_negative": None,
            }
            assert "expected" not in row
            assert "notes" not in row
            assert "proposed" not in row
            assert "baseline" not in row
            assert "score" not in row
            assert row["response_text"]


def test_double_annotation_requires_third_party_adjudication_and_preserves_audit(tmp_path):
    from evaluation.annotation_workflow import (
        export_annotation_templates,
        finalize_annotations,
    )

    cases_path = tmp_path / "held_out.jsonl"
    _write_jsonl(cases_path, [
        _case("case-1", "family-1", {
            "kasparro_mentioned": True,
            "kasparro_recommended": True,
            "kasparro_negative": False,
        }),
        _case("case-2", "family-2", {
            "kasparro_mentioned": True,
            "kasparro_recommended": False,
            "kasparro_negative": False,
        }),
    ])

    reviewer_a_path, reviewer_b_path = [
        Path(value) for value in export_annotation_templates(
            cases_path=cases_path,
            output_dir=tmp_path / "packets",
            reviewer_ids=("reviewer_a", "reviewer_b"),
            seed=17,
        )
    ]

    reviewer_a = _read_jsonl(reviewer_a_path)
    reviewer_b = _read_jsonl(reviewer_b_path)
    labels = {
        "case-1": {
            "kasparro_mentioned": True,
            "kasparro_recommended": True,
            "kasparro_negative": False,
        },
        "case-2": {
            "kasparro_mentioned": True,
            "kasparro_recommended": False,
            "kasparro_negative": False,
        },
    }
    for row in reviewer_a:
        row["labels"] = labels[row["case_id"]]
        row["rationale"] = "The response explicitly evaluates Kasparro."
    for row in reviewer_b:
        row["labels"] = (
            labels[row["case_id"]]
            if row["case_id"] == "case-1"
            else {
                "kasparro_mentioned": False,
                "kasparro_recommended": False,
                "kasparro_negative": False,
            }
        )
        row["rationale"] = "The reviewer applied the label definitions."
    _write_jsonl(reviewer_a_path, reviewer_a)
    _write_jsonl(reviewer_b_path, reviewer_b)

    adjudication_template = tmp_path / "adjudication_required.jsonl"
    output_path = tmp_path / "adjudicated.jsonl"
    summary_path = tmp_path / "agreement.json"

    with pytest.raises(ValueError, match="require third-reviewer adjudication"):
        finalize_annotations(
            reviewer_a_path=reviewer_a_path,
            reviewer_b_path=reviewer_b_path,
            cases_path=cases_path,
            output_path=output_path,
            summary_path=summary_path,
            adjudication_template_path=adjudication_template,
        )

    pending = _read_jsonl(adjudication_template)
    assert [row["case_id"] for row in pending] == ["case-2"]
    pending[0]["adjudicator_id"] = "reviewer_c"
    pending[0]["labels"] = labels["case-2"]
    pending[0]["rationale"] = "The source directly names Kasparro."
    adjudication_path = tmp_path / "adjudication.jsonl"
    _write_jsonl(adjudication_path, pending)

    summary = finalize_annotations(
        reviewer_a_path=reviewer_a_path,
        reviewer_b_path=reviewer_b_path,
        cases_path=cases_path,
        adjudication_path=adjudication_path,
        output_path=output_path,
        summary_path=summary_path,
        adjudication_template_path=adjudication_template,
    )

    finalized = {row["case_id"]: row for row in _read_jsonl(output_path)}
    assert finalized["case-2"]["expected"] == labels["case-2"]
    assert finalized["case-2"]["provisional_expected"] == {
        "kasparro_mentioned": True,
        "kasparro_recommended": False,
        "kasparro_negative": False,
    }
    assert finalized["case-2"]["annotation_status"] == (
        "independently_double_annotated_and_adjudicated"
    )
    audit = finalized["case-2"]["annotation_audit"]
    assert audit["reviewers_agreed"] is False
    assert audit["reviewer_a"]["annotator_id"] == "reviewer_a"
    assert audit["reviewer_b"]["annotator_id"] == "reviewer_b"
    assert audit["adjudication"]["annotator_id"] == "reviewer_c"
    assert summary["total_cases"] == 2
    assert summary["unanimous_cases"] == 1
    assert summary["disputed_cases"] == 1
    assert summary["adjudicated_cases"] == 1
    assert summary["per_label_agreement"]["kasparro_mentioned"]["raw_agreement"] == 0.5
    assert summary_path.is_file()


def test_annotation_finalization_rejects_same_reviewer_identity(tmp_path):
    from evaluation.annotation_workflow import finalize_annotations

    cases_path = tmp_path / "cases.jsonl"
    _write_jsonl(cases_path, [
        _case("case-1", "family-1", {
            "kasparro_mentioned": True,
            "kasparro_recommended": False,
            "kasparro_negative": False,
        })
    ])
    packet = [{
        "annotator_id": "same_reviewer",
        "case_id": "case-1",
        "engine": "chatgpt",
        "prompt_text": "Should I consider Kasparro?",
        "response_text": "Kasparro is worth considering for B2B SaaS teams.",
        "labels": {
            "kasparro_mentioned": True,
            "kasparro_recommended": False,
            "kasparro_negative": False,
        },
    }]
    reviewer_a = tmp_path / "reviewer_a.jsonl"
    reviewer_b = tmp_path / "reviewer_b.jsonl"
    _write_jsonl(reviewer_a, packet)
    _write_jsonl(reviewer_b, packet)

    with pytest.raises(ValueError, match="distinct reviewer IDs"):
        finalize_annotations(
            reviewer_a_path=reviewer_a,
            reviewer_b_path=reviewer_b,
            cases_path=cases_path,
            output_path=tmp_path / "out.jsonl",
            summary_path=tmp_path / "summary.json",
        )


def test_held_out_metrics_report_coverage_and_do_not_hide_provider_failures(monkeypatch, tmp_path):
    import evaluation.run_eval as run_eval

    real_classifier = run_eval.ReplayClassifier

    class OneFailureClassifier:
        def __init__(self):
            self.delegate = real_classifier()
            self.classifier_version = self.delegate.classifier_version

        def classify(self, response_id, engine, answer_text, prompt_text=None):
            if response_id == "heldout-response-001":
                return SimpleNamespace(
                    status="failed",
                    failure_reason="simulated provider outage",
                )
            return self.delegate.classify(
                response_id,
                engine,
                answer_text,
                prompt_text=prompt_text,
            )

    monkeypatch.setattr(run_eval, "ReplayClassifier", OneFailureClassifier)
    result = run_eval.run_evaluation(
        execution_mode="replay",
        split="held_out",
        output_dir=str(tmp_path),
    )

    coverage = result["coverage_metrics"]
    assert coverage["total_cases"] == 30
    assert coverage["successful_classifier_calls"] == 29
    assert coverage["failed_classifier_calls"] == 1
    assert coverage["coverage_rate"] == pytest.approx(29 / 30, abs=1e-4)
    assert result["proposed_metrics"]["total_cases"] == 29
    assert coverage["coverage_adjusted_exact_match_rate"] == pytest.approx(
        result["proposed_metrics"]["exact_matches"] / 30,
        abs=1e-4,
    )
    assert result["baseline_metrics_all_cases"]["total_cases"] == 30
    assert result["counts"]["annotation_status"] == "provisional_single_annotator"

    report = (tmp_path / "eval_comparison_report_held_out.md").read_text(encoding="utf-8")
    assert "Execution Coverage" in report
    assert "Coverage-adjusted exact-match agreement" in report
    assert "provisional_single_annotator" in report
