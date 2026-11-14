import json

import pytest

from app.config import Settings
from app.llm.base import ClassificationResult, EvidenceItem
from app.llm.provider import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_LLM_BASE_URL,
    ProviderClassifier,
)


def test_gemini_provider_defaults_to_compatible_endpoint_and_flash_lite_model():
    provider = ProviderClassifier(
        Settings(
            LLM_PROVIDER="gemini",
            LLM_API_KEY="test-secret",
        )
    )

    assert provider.provider == "gemini"
    assert provider.model == "gemini-3.5-flash-lite"
    assert provider.base_url == DEFAULT_GEMINI_BASE_URL
    assert provider.base_url.endswith("/v1beta/openai/chat/completions")


def test_custom_provider_url_overrides_gemini_default():
    custom_url = "https://gateway.example.test/v1/chat/completions"
    provider = ProviderClassifier(
        Settings(
            LLM_PROVIDER="gemini",
            LLM_MODEL="custom-gemini-model",
            LLM_API_KEY="test-secret",
            LLM_BASE_URL=custom_url,
        )
    )

    assert provider.base_url == custom_url
    assert provider.model == "custom-gemini-model"


def test_openai_provider_keeps_existing_default_endpoint():
    provider = ProviderClassifier(
        Settings(
            LLM_PROVIDER="openai",
            LLM_API_KEY="test-secret",
        )
    )

    assert provider.base_url == DEFAULT_LLM_BASE_URL
    assert provider.model == "gpt-4o-mini"


def test_provider_smoke_test_processes_one_archived_response_and_audits_quotes(
    tmp_path, monkeypatch
):
    import evaluation.provider_smoke_test as smoke

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    response_id = "archived-response-001"
    answer = "Kasparro is worth evaluating for mid-market B2B SaaS teams."
    (data_dir / "responses.jsonl").write_text(
        json.dumps({
            "response_id": response_id,
            "prompt_id": "prompt-001",
            "engine": "chatgpt",
            "answer_text": answer,
        }) + "\n",
        encoding="utf-8",
    )
    (data_dir / "prompts.jsonl").write_text(
        json.dumps({
            "prompt_id": "prompt-001",
            "text": "Should a SaaS team evaluate Kasparro?",
        }) + "\n",
        encoding="utf-8",
    )

    class FakeProviderClassifier:
        def __init__(self, settings):
            self.provider = "gemini"
            self.model = "gemini-3.5-flash-lite"
            self.base_url = DEFAULT_GEMINI_BASE_URL
            self.classifier_version = "test-v1"

        def classify(self, response_id, engine, answer_text, prompt_text=None):
            assert response_id == "archived-response-001"
            assert engine == "chatgpt"
            assert answer_text == answer
            assert prompt_text == "Should a SaaS team evaluate Kasparro?"
            return ClassificationResult(
                response_id=response_id,
                engine=engine,
                status="success",
                kasparro_absent=False,
                kasparro_mentioned=True,
                kasparro_recommended=True,
                kasparro_negative=False,
                evidence=[
                    EvidenceItem(
                        excerpt="Kasparro is worth evaluating",
                        location="answer_text",
                    ),
                    EvidenceItem(
                        excerpt="Kasparro guarantees first place",
                        location="answer_text",
                    ),
                ],
                confidence=0.91,
                execution_mode="real_model",
                classifier_version="test-v1",
            )

    monkeypatch.setattr(smoke, "ProviderClassifier", FakeProviderClassifier)
    settings = Settings(
        EXECUTION_MODE="real_model",
        LLM_PROVIDER="gemini",
        LLM_MODEL="gemini-3.5-flash-lite",
        LLM_API_KEY="do-not-print-this-secret",
    )

    summary = smoke.run_smoke_test(
        responses_path=data_dir / "responses.jsonl",
        prompts_path=data_dir / "prompts.jsonl",
        settings_override=settings,
    )

    assert summary["status"] == "success"
    assert summary["execution_mode"] == "real_model"
    assert summary["response"]["response_id"] == response_id
    assert summary["classification"]["kasparro_recommended"] is True
    assert summary["evidence_validation"] == {
        "candidate_count": 2,
        "accepted_exact_or_normalized_matches": 1,
        "rejected": 1,
    }


def test_provider_smoke_test_refuses_replay_mode_without_calling_provider(monkeypatch):
    import evaluation.provider_smoke_test as smoke

    class UnexpectedProvider:
        def __init__(self, settings):
            raise AssertionError("Provider must not be constructed in replay mode")

    monkeypatch.setattr(smoke, "ProviderClassifier", UnexpectedProvider)

    with pytest.raises(ValueError, match="EXECUTION_MODE=real_model"):
        smoke.run_smoke_test(
            settings_override=Settings(
                EXECUTION_MODE="replay",
                LLM_API_KEY="test-secret",
            )
        )


def test_provider_smoke_test_rejects_missing_api_key():
    import evaluation.provider_smoke_test as smoke

    with pytest.raises(ValueError, match="LLM_API_KEY is missing"):
        smoke.run_smoke_test(
            settings_override=Settings(
                EXECUTION_MODE="real_model",
                LLM_PROVIDER="gemini",
                LLM_API_KEY="",
            )
        )


def test_gemini_provider_sends_bearer_auth_and_json_chat_completion(monkeypatch):
    import json
    import app.llm.provider as provider_module

    calls = []

    class FakeResponse:
        status_code = 200
        headers = {}

        def json(self):
            output = {
                "kasparro_absent": False,
                "kasparro_mentioned": True,
                "kasparro_recommended": True,
                "kasparro_negative": False,
                "competitors": [],
                "recommendation_position": None,
                "evidence": [{
                    "excerpt": "Kasparro is worth considering.",
                    "location": "answer_text",
                }],
                "confidence": 0.93,
            }
            return {
                "choices": [{"message": {"content": json.dumps(output)}}],
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            calls.append({"url": url, "headers": headers, "payload": json})
            return FakeResponse()

    monkeypatch.setattr(provider_module.httpx, "Client", FakeClient)
    classifier = ProviderClassifier(
        Settings(LLM_PROVIDER="gemini", LLM_API_KEY="local-test-key", LLM_MAX_RETRIES=0)
    )
    result = classifier.classify(
        "gemini-smoke-response",
        "chatgpt",
        "Kasparro is worth considering.",
    )

    assert len(calls) == 1
    assert calls[0]["url"] == DEFAULT_GEMINI_BASE_URL
    assert calls[0]["headers"]["Authorization"] == "Bearer local-test-key"
    assert calls[0]["payload"]["model"] == "gemini-3.5-flash-lite"
    assert calls[0]["payload"]["response_format"] == {"type": "json_object"}
    assert result.status == "success"
    assert result.execution_mode == "real_model"
    assert result.kasparro_recommended is True
