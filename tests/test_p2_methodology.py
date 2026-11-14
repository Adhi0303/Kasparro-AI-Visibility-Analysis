import json
from pathlib import Path


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_supplied_development_cases_are_documented_and_cover_all_engines():
    cases = _jsonl("evaluation/cases.jsonl")
    supplied = [case for case in cases if case.get("source_type") == "supplied"]
    assert len(supplied) >= 8
    assert {case["engine"] for case in supplied} >= {"chatgpt", "gemini", "aimode"}
    for case in supplied:
        annotation = case["annotation"]
        assert annotation["method"] == "preexisting_project_reference_labels_provenance_unverified"
        assert annotation["annotator_role"] == "not_recorded"
        assert annotation["label_set_version"] == "kasparro-provider-labels-v1"
        assert annotation["category"]
        assert annotation["rationale"]
        assert set(case["expected"]) == {
            "kasparro_mentioned", "kasparro_recommended", "kasparro_negative"
        }


def test_two_required_edge_cases_are_explicit_and_separate_from_supplied():
    cases = _jsonl("evaluation/cases.jsonl")
    by_id = {case["case_id"]: case for case in cases}
    for case_id in ("synthetic-001", "synthetic-002"):
        assert by_id[case_id]["source_type"] == "synthetic"
        assert by_id[case_id]["edge_case_required"] is True
        assert by_id[case_id]["split_role"] == "development_regression_edge_case"


def test_development_and_held_out_prompt_families_do_not_overlap():
    development = _jsonl("evaluation/cases.jsonl")
    held_out = _jsonl("evaluation/held_out_cases.jsonl")
    dev_prompts = {case.get("prompt_id") for case in development}
    held_prompts = {case.get("prompt_id") for case in held_out}
    assert not (dev_prompts & held_prompts)
