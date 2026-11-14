"""Run one live provider call against one archived source response.

This is a safe configuration smoke test. It does not run the full evaluation
or print API credentials / full source text.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.evidence import find_evidence_match
from app.llm.provider import ProviderClassifier


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Required source file not found: {source}")
    rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{source}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{source}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def load_archived_response(
    response_id: str | None = None,
    responses_path: str | Path = "data/responses.jsonl",
    prompts_path: str | Path | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Load exactly one real archived response and its originating prompt."""
    responses = _load_jsonl(responses_path)
    selected = None
    if response_id:
        matches = [row for row in responses if row.get("response_id") == response_id]
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one archived response for ID {response_id!r}; "
                f"found {len(matches)}"
            )
        selected = matches[0]
    else:
        selected = next(
            (row for row in responses if isinstance(row.get("answer_text"), str) and row["answer_text"].strip()),
            None,
        )
    if selected is None:
        raise ValueError("No response with non-empty answer_text exists in the archive")

    answer_text = selected.get("answer_text")
    if not isinstance(answer_text, str) or not answer_text.strip():
        raise ValueError(f"Response {selected.get('response_id')} has no answer_text")

    prompt_file = Path(prompts_path) if prompts_path else Path(responses_path).with_name("prompts.jsonl")
    prompt_by_id: dict[str, str] = {}
    if prompt_file.is_file():
        for prompt in _load_jsonl(prompt_file):
            prompt_id = prompt.get("prompt_id")
            prompt_text = prompt.get("text")
            if isinstance(prompt_id, str) and isinstance(prompt_text, str):
                prompt_by_id[prompt_id] = prompt_text

    prompt_text = prompt_by_id.get(selected.get("prompt_id"))
    return selected, prompt_text


def run_smoke_test(
    *,
    response_id: str | None = None,
    responses_path: str | Path = "data/responses.jsonl",
    prompts_path: str | Path | None = None,
    settings_override: Settings | None = None,
) -> dict[str, Any]:
    settings = settings_override or get_settings()
    if settings.EXECUTION_MODE != "real_model":
        raise ValueError(
            "Set EXECUTION_MODE=real_model in your local .env before running the provider smoke test."
        )
    if not settings.LLM_API_KEY or not settings.LLM_API_KEY.strip():
        raise ValueError("LLM_API_KEY is missing. Add it to your local .env file; never commit it.")

    response, prompt_text = load_archived_response(
        response_id=response_id,
        responses_path=responses_path,
        prompts_path=prompts_path,
    )
    answer_text = response["answer_text"]
    classifier = ProviderClassifier(settings)

    started = time.perf_counter()
    result = classifier.classify(
        response_id=response["response_id"],
        engine=response.get("engine", "unknown"),
        answer_text=answer_text,
        prompt_text=prompt_text,
    )
    elapsed_seconds = round(time.perf_counter() - started, 3)

    accepted_evidence = 0
    rejected_evidence = 0
    for evidence in result.evidence:
        match = find_evidence_match(
            evidence.excerpt,
            answer_text,
            location=evidence.location,
        )
        if match.get("valid"):
            accepted_evidence += 1
        else:
            rejected_evidence += 1

    return {
        "execution_mode": result.execution_mode,
        "status": result.status,
        "provider": classifier.provider,
        "model": classifier.model,
        "endpoint": classifier.base_url,
        "classifier_version": result.classifier_version,
        "response": {
            "response_id": response["response_id"],
            "engine": response.get("engine", "unknown"),
            "answer_characters": len(answer_text),
            "prompt_included": bool(prompt_text),
        },
        "classification": {
            "kasparro_mentioned": result.kasparro_mentioned,
            "kasparro_recommended": result.kasparro_recommended,
            "kasparro_negative": result.kasparro_negative,
            "competitors": result.competitors,
            "confidence": result.confidence,
        } if result.status == "success" else None,
        "evidence_validation": {
            "candidate_count": len(result.evidence),
            "accepted_exact_or_normalized_matches": accepted_evidence,
            "rejected": rejected_evidence,
        },
        "elapsed_seconds": elapsed_seconds,
        "failure_reason": result.failure_reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test the configured real-model provider on one archived answer."
    )
    parser.add_argument(
        "--response-id",
        help="Optional response ID from data/responses.jsonl. Defaults to the first non-empty archived answer.",
    )
    parser.add_argument("--responses", default="data/responses.jsonl")
    parser.add_argument("--prompts", default="data/prompts.jsonl")
    args = parser.parse_args()

    try:
        summary = run_smoke_test(
            response_id=args.response_id,
            responses_path=args.responses,
            prompts_path=args.prompts,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Provider smoke test could not run: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2))
    if summary["status"] != "success":
        return 1

    print("\nProvider smoke test passed: one archived response was processed by the configured live model.")
    print("No full-dataset evaluation was started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
