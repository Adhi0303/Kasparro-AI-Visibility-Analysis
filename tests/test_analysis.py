import pytest
from app.llm.replay import ReplayClassifier
from app.llm.provider import ProviderClassifier
from app.config import Settings


def test_replay_classifier_mention_and_negative():
    classifier = ReplayClassifier()
    text = (
        "Based on my research, Kasparro is not a widely recognized, top-tier agency "
        "in the AI visibility space. I would exercise caution and scamadviser checks."
    )
    res = classifier.classify("resp-1", "chatgpt", text)
    assert res.status == "success"
    assert res.kasparro_mentioned is True
    assert res.kasparro_absent is False
    assert res.kasparro_negative is True
    assert res.execution_mode == "replay"
    assert len(res.evidence) > 0
    # Every evidence excerpt must exist verbatim in the source text
    for ev in res.evidence:
        assert ev.excerpt in text


def test_replay_classifier_absent():
    classifier = ReplayClassifier()
    text = "Here are the top AISO agencies: Profound, Peec AI, and Otterly."
    res = classifier.classify("resp-2", "gemini", text)
    assert res.status == "success"
    assert res.kasparro_absent is True
    assert res.kasparro_mentioned is False
    assert res.kasparro_recommended is False
    assert "profound" in res.competitors


def test_replay_classifier_simulated_timeout():
    classifier = ReplayClassifier()
    res = classifier.classify("resp-timeout", "aimode", "Some answer", failure_scenario="permanent_timeout")
    assert res.status == "failed"
    assert "timeout" in res.failure_reason.lower()
    assert res.kasparro_mentioned is False
    assert res.kasparro_absent is False


def test_replay_classifier_simulated_malformed():
    classifier = ReplayClassifier()
    res = classifier.classify("resp-malformed", "aimode", "Some answer", failure_scenario="malformed")
    assert res.status == "failed"
    assert "malformed" in res.failure_reason.lower()


def test_provider_classifier_without_key():
    settings = Settings(LLM_API_KEY="")
    provider = ProviderClassifier(settings)
    res = provider.classify("resp-keyless", "chatgpt", "Some text")
    assert res.status == "failed"
    assert "not configured" in res.failure_reason


def test_all_diagnostic_evidence_verbatim_integrity():
    import json
    import os
    from app.diagnostics import get_default_diagnostics

    responses_path = "data/responses.jsonl"
    assert os.path.exists(responses_path), "data/responses.jsonl must exist"

    with open(responses_path, "r", encoding="utf-8") as f:
        responses = {json.loads(line)["response_id"]: json.loads(line) for line in f}

    diagnostics = get_default_diagnostics()
    assert len(diagnostics) == 3, "Expected 3 default diagnostics"

    for d in diagnostics:
        for ev in d["evidence"]:
            rid = ev["response_id"]
            excerpt = ev["excerpt"]
            assert rid in responses, f"Response ID '{rid}' cited in diagnostic '{d['title']}' not found in dataset"
            source_text = responses[rid].get("answer_text", "")
            assert excerpt in source_text, (
                f"Evidence excerpt in diagnostic '{d['title']}' is not a verbatim substring of response '{rid}':\n"
                f"Excerpt: {repr(excerpt)}"
            )


