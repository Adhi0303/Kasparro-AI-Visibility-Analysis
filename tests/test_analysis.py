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


def test_find_evidence_match_exact_and_offsets():
    from app.evidence import find_evidence_match, validate_evidence

    source_text = "Evaluators noted that Kasparro offers clear scoring formulas, while Profound leads enterprise share."
    excerpt = "Kasparro offers clear scoring formulas"
    match = find_evidence_match(excerpt, source_text)

    assert match["valid"] is True
    assert match["match_type"] == "exact"
    assert match["start_offset"] == 22
    assert match["end_offset"] == 60
    assert source_text[match["start_offset"]:match["end_offset"]] == excerpt

    is_valid, reason = validate_evidence(excerpt, source_text)
    assert is_valid is True
    assert reason is None


def test_find_evidence_match_whitespace_normalized_maps_original_offsets():
    from app.evidence import find_evidence_match, validate_evidence

    source_text = "Overview:\n  Kasparro   integrates   with\tChatGPT and Gemini reliably."
    excerpt = "Kasparro integrates with ChatGPT"
    match = find_evidence_match(excerpt, source_text)

    assert match["valid"] is True
    assert match["match_type"] == "normalized_whitespace"
    start, end = match["start_offset"], match["end_offset"]
    assert start == source_text.index("Kasparro")
    assert source_text[start:end] == "Kasparro   integrates   with\tChatGPT"

    is_valid, reason = validate_evidence(excerpt, source_text)
    assert is_valid is True
    assert reason is None


def test_find_evidence_match_leading_trailing_whitespace_preserved():
    from app.evidence import find_evidence_match, validate_evidence

    source_text = "Summary: Kasparro provides structured diagnostics."
    excerpt = "   Kasparro provides structured   "
    match = find_evidence_match(excerpt, source_text)

    assert match["valid"] is True
    assert source_text[match["start_offset"]:match["end_offset"]] == "Kasparro provides structured"
    assert validate_evidence(excerpt, source_text) == (True, None)


def test_find_evidence_match_rejections():
    from app.evidence import find_evidence_match, validate_evidence

    source_text = "Kasparro provides reproducible analytics."

    fabricated = find_evidence_match("Kasparro guarantees #1 rankings overnight.", source_text)
    assert fabricated["valid"] is False
    assert fabricated["start_offset"] is None
    assert fabricated["end_offset"] is None
    assert "not found" in fabricated["rejection_reason"].lower()

    empty_exc = find_evidence_match("   \n\t ", source_text)
    assert empty_exc["valid"] is False
    assert "empty" in empty_exc["rejection_reason"].lower()

    empty_src = find_evidence_match("Kasparro", "")
    assert empty_src["valid"] is False
    assert "empty" in empty_src["rejection_reason"].lower()

    ok, err = validate_evidence("Fabricated text", source_text)
    assert ok is False
    assert err is not None and "not found" in err.lower()


def test_centralized_evidence_validation_records_rejected_and_accepted(monkeypatch):
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import Dataset, Response as DBResponse, ResponseResult
    from app.classification import execute_analysis
    from app.llm.base import ClassificationResult, EvidenceItem, LLMBase

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        ds = Dataset(name="phase1-audit-test", source_hash="hash123", validation_status="valid")
        db.add(ds)
        db.flush()

        answer_text = "Analysts report that   Kasparro provides\nstructured scoring for B2B buyers."
        db_resp = DBResponse(
            dataset_id=ds.id,
            source_response_id="resp-audit-001",
            prompt_id="kasparro:ai_shortlisting:001",
            engine="chatgpt",
            raw_payload=json.dumps({
                "response_id": "resp-audit-001",
                "prompt_id": "kasparro:ai_shortlisting:001",
                "engine": "chatgpt",
                "answer_text": answer_text,
            }),
        )
        db.add(db_resp)
        db.commit()

        exact_quote = "Analysts report that"
        normalized_quote = "Kasparro provides structured scoring"
        fabricated_quote = "Kasparro is the best tool in history"

        class StubClassifier(LLMBase):
            def classify(self, response_id, engine, answer_text, failure_scenario=None):
                return ClassificationResult(
                    response_id=response_id,
                    engine=engine,
                    status="success",
                    kasparro_absent=False,
                    kasparro_mentioned=True,
                    kasparro_recommended=True,
                    kasparro_negative=False,
                    competitors=[],
                    evidence=[
                        EvidenceItem(excerpt=exact_quote, location="answer_text"),
                        EvidenceItem(excerpt=normalized_quote, location="answer_text"),
                        EvidenceItem(excerpt=fabricated_quote, location="answer_text"),
                        EvidenceItem(excerpt="   ", location="answer_text"),
                    ],
                    confidence=0.9,
                    execution_mode="replay",
                    classifier_version="v1",
                )

        monkeypatch.setattr("app.classification.get_classifier", lambda **kwargs: StubClassifier())

        analysis = execute_analysis(db, dataset_id=ds.id, execution_mode="replay")
        row = db.query(ResponseResult).filter(ResponseResult.analysis_id == analysis.id).first()
        assert row is not None

        accepted = json.loads(row.evidence_json)
        assert len(accepted) == 2
        assert accepted[0]["excerpt"] == exact_quote
        assert accepted[0]["match_type"] == "exact"
        assert accepted[0]["validation_status"] == "valid"
        assert answer_text[accepted[0]["start_offset"]:accepted[0]["end_offset"]] == exact_quote

        assert accepted[1]["excerpt"] == normalized_quote
        assert accepted[1]["match_type"] == "normalized_whitespace"
        assert accepted[1]["validation_status"] == "valid"
        assert answer_text[accepted[1]["start_offset"]:accepted[1]["end_offset"]] == "Kasparro provides\nstructured scoring"

        accepted_excerpts = [item["excerpt"] for item in accepted]
        assert fabricated_quote not in accepted_excerpts
        assert "   " not in accepted_excerpts

        labels = json.loads(row.labels_json)
        audit = labels["evidence_validation"]
        assert audit["accepted_count"] == 2
        assert audit["rejected_count"] == 2
        assert len(audit["accepted"]) == 2
        assert len(audit["rejected"]) == 2
        assert audit["rejected"][0]["excerpt"] == fabricated_quote
        assert audit["rejected"][0]["validation_status"] == "rejected"
        assert "not found" in audit["rejected"][0]["rejection_reason"].lower()
        assert audit["rejected"][1]["validation_status"] == "rejected"
        assert "empty" in audit["rejected"][1]["rejection_reason"].lower()
    finally:
        db.close()


def test_provider_preserves_candidates_and_central_validation_audits(monkeypatch):
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import Dataset, Response as DBResponse, ResponseResult
    from app.classification import execute_analysis, _audit_evidence_candidates
    import app.llm.provider as provider_mod

    source_text = "Evaluations confirm Kasparro appears in ChatGPT responses."
    mock_payload = {
        "kasparro_absent": False,
        "kasparro_mentioned": True,
        "kasparro_recommended": False,
        "kasparro_negative": False,
        "competitors": [],
        "recommendation_position": None,
        "evidence": [
            {"excerpt": "Kasparro appears in ChatGPT responses.", "location": "answer_text"},
            {"excerpt": "Invented sentence from LLM hallucination", "location": "answer_text"},
            {"excerpt": "", "location": "answer_text"},
        ],
        "confidence": 0.91,
    }

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(mock_payload)}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(provider_mod.httpx, "Client", FakeClient)

    # 1. Provider retains valid-schema candidate strings rather than silently dropping invalid ones
    settings = Settings(LLM_API_KEY="test-key")
    provider = ProviderClassifier(settings)
    res = provider.classify("resp-prov-1", "chatgpt", source_text)
    assert res.status == "success"
    assert len(res.evidence) == 3
    assert any(ev.excerpt == "Invented sentence from LLM hallucination" for ev in res.evidence)

    # 2. Central validation in execute_analysis accepts only valid excerpts & audits all rejected candidates
    monkeypatch.setattr("app.classification.get_settings", lambda: Settings(LLM_API_KEY="test-key"))

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        ds = Dataset(name="prov-audit-test", source_hash="hash456", validation_status="valid")
        db.add(ds)
        db.flush()
        db_resp = DBResponse(
            dataset_id=ds.id,
            source_response_id="resp-prov-1",
            prompt_id="kasparro:ai_shortlisting:001",
            engine="chatgpt",
            raw_payload=json.dumps({
                "response_id": "resp-prov-1",
                "prompt_id": "kasparro:ai_shortlisting:001",
                "engine": "chatgpt",
                "answer_text": source_text,
            }),
        )
        db.add(db_resp)
        db.commit()

        analysis = execute_analysis(db, dataset_id=ds.id, execution_mode="real_model")
        row = db.query(ResponseResult).filter(ResponseResult.analysis_id == analysis.id).first()

        accepted = json.loads(row.evidence_json)
        assert len(accepted) == 1
        assert accepted[0]["excerpt"] == "Kasparro appears in ChatGPT responses."
        assert source_text[accepted[0]["start_offset"]:accepted[0]["end_offset"]] == accepted[0]["excerpt"]

        labels = json.loads(row.labels_json)
        audit = labels["evidence_validation"]
        assert audit["accepted_count"] == 1
        assert audit["rejected_count"] == 2
        assert all(item["validation_status"] == "rejected" for item in audit["rejected"])
        assert all(item["rejection_reason"] for item in audit["rejected"])
    finally:
        db.close()

    # 3. Direct malformed items passed to centralized auditor are isolated cleanly
    acc_direct, rej_direct = _audit_evidence_candidates(
        [{"excerpt": "Kasparro appears"}, {"location": "answer_text"}, 12345],
        source_text,
    )
    assert len(acc_direct) == 1
    assert len(rej_direct) == 2


@pytest.mark.parametrize(
    "answer_text, exp_mentioned, exp_recommended, exp_negative",
    [
        ("Kasparro is a strong AI visibility platform.", True, True, False),
        ("Kasparro lacks independent case studies.", True, False, True),
        ("I recommend Profound over Kasparro.", True, False, False),
        ("The user asked about Kasparro.", False, False, False),
        ("You mentioned Kasparro in your question. Profound and Peec AI lead here.", False, False, False),
        ('Prompt: "What does Kasparro do?" Profound is widely cited instead.', False, False, False),
        ("Profound has negative reviews. Kasparro offers monitoring.", True, False, False),
        ("Kasparro is not recommended because of poor evidence.", True, False, True),
        ("There is insufficient public information to assess Kasparro.", True, False, False),
        ("Kasparro is worth considering for B2B SaaS.", True, True, False),
        ("Kasparro and Profound are frequently compared.", True, False, False),
        ("I recommend Kasparro, but its reliability is questionable.", True, True, True),
        ("Kasparro was mentioned alongside other tools.", True, False, False),
        ("AI visibility tracking is still evolving and unreliable. Kasparro provides structured analytics.", True, False, False),
        ("Unlike Profound, which lacks case studies, Kasparro is worth evaluating.", True, True, False),
        ("I recommend Profound. Kasparro is emerging, though Kasparro offers monitoring.", True, False, False),
        ("Kasparro is reliable, while Profound has negative reviews from teams.", True, False, False),
        ("I do not recommend Kasparro due to unproven metrics.", True, False, True),
    ],
)
def test_replay_classifier_contextual_accuracy_and_target_attribution(
    answer_text,
    exp_mentioned,
    exp_recommended,
    exp_negative,
):
    classifier = ReplayClassifier()
    res = classifier.classify("resp-ctx", "chatgpt", answer_text)
    assert res.status == "success"
    assert res.kasparro_mentioned is exp_mentioned
    assert res.kasparro_absent is (not exp_mentioned)
    assert res.kasparro_recommended is exp_recommended
    assert res.kasparro_negative is exp_negative


def test_provider_strict_schema_validation_and_configurable_base_url(monkeypatch):
    import json
    import httpx
    import app.llm.provider as provider_mod

    captured_urls = []
    mock_body = {}
    mock_status = 200
    raise_timeout = False

    class FakeResp:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self._body = body
            self.text = json.dumps(body) if isinstance(body, dict) else str(body)

        def json(self):
            return self._body

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured_urls.append(url)
            if raise_timeout:
                raise httpx.TimeoutException("Timed out")
            return FakeResp(mock_status, mock_body)

    monkeypatch.setattr(provider_mod.httpx, "Client", FakeClient)

    valid_payload = {
        "kasparro_absent": False,
        "kasparro_mentioned": True,
        "kasparro_recommended": True,
        "kasparro_negative": False,
        "competitors": ["profound"],
        "recommendation_position": 2,
        "evidence": [{"excerpt": "Kasparro works well", "location": "answer_text"}],
        "confidence": 0.88,
    }

    # 1. Valid JSON response using custom LLM_BASE_URL
    custom_url = "http://localhost:11434/v1/chat/completions"
    mock_body = {"choices": [{"message": {"content": json.dumps(valid_payload)}}]}
    provider = ProviderClassifier(
        Settings(LLM_API_KEY="k", LLM_BASE_URL=custom_url, LLM_MODEL="local-llama", LLM_MAX_RETRIES=0)
    )
    ok_res = provider.classify("r1", "chatgpt", "Kasparro works well")
    assert ok_res.status == "success"
    assert ok_res.recommendation_position == 2
    assert captured_urls[-1] == custom_url

    # 2. Default OpenAI endpoint when LLM_BASE_URL is None
    default_provider = ProviderClassifier(Settings(LLM_API_KEY="k", LLM_MAX_RETRIES=0))
    ok_def = default_provider.classify("r2", "chatgpt", "Kasparro works well")
    assert ok_def.status == "success"
    assert captured_urls[-1] == provider_mod.DEFAULT_LLM_BASE_URL

    # 3. Reject invalid LLM outputs strictly rather than coercing them
    invalid_payloads = [
        # Missing required fields
        {"kasparro_mentioned": True},
        # String "false" must NOT coerce to True
        {**valid_payload, "kasparro_mentioned": "false"},
        # Out-of-bounds / invalid confidence
        {**valid_payload, "confidence": 1.5},
        {**valid_payload, "confidence": -0.1},
        {**valid_payload, "confidence": True},
        # Invalid competitors type
        {**valid_payload, "competitors": "profound"},
        # Invalid recommendation position
        {**valid_payload, "recommendation_position": 0},
        {**valid_payload, "recommendation_position": True},
        # Malformed evidence items
        {**valid_payload, "evidence": [12345]},
        {**valid_payload, "evidence": [{"location": "answer_text"}]},
        {**valid_payload, "evidence": "not a list"},
    ]

    for bad in invalid_payloads:
        mock_body = {"choices": [{"message": {"content": json.dumps(bad)}}]}
        bad_res = default_provider.classify("r-bad", "chatgpt", "Kasparro works well")
        assert bad_res.status == "failed", f"Expected failure for payload: {bad}"
        assert bad_res.failure_reason

    # 4. Missing message content / invalid JSON
    mock_body = {"choices": [{"message": {"content": ""}}]}
    empty_res = default_provider.classify("r-empty", "chatgpt", "Kasparro works well")
    assert empty_res.status == "failed"

    # 5. HTTP error status
    mock_status = 502
    mock_body = {"error": "Bad gateway"}
    http_err = default_provider.classify("r-http", "chatgpt", "Kasparro works well")
    assert http_err.status == "failed"
    assert "502" in http_err.failure_reason

    # 6. Timeout handling
    mock_status = 200
    raise_timeout = True
    to_res = default_provider.classify("r-to", "chatgpt", "Kasparro works well")
    assert to_res.status == "failed"
    assert "timed out" in to_res.failure_reason.lower()


def test_run_eval_separates_replay_and_real_model(monkeypatch, tmp_path):
    import json
    import os
    from evaluation.run_eval import run_evaluation
    import app.llm.provider as provider_mod

    # 1. Default replay run writes eval_results.json in output dir
    replay_dir = tmp_path / "replay_out"
    replay_res = run_evaluation(execution_mode="replay", output_dir=str(replay_dir))
    assert replay_res["execution_metadata"]["execution_mode"] == "replay"
    assert os.path.exists(replay_dir / "eval_results.json")
    assert not os.path.exists(replay_dir / "eval_provider_results.json")

    # 2. Explicit real_model run writes ONLY eval_provider_results.json and never mixes with replay
    class FakeResp:
        status_code = 200

        def json(self):
            payload = {
                "kasparro_absent": True,
                "kasparro_mentioned": False,
                "kasparro_recommended": False,
                "kasparro_negative": False,
                "competitors": [],
                "recommendation_position": None,
                "evidence": [],
                "confidence": 0.9,
            }
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            return FakeResp()

    monkeypatch.setattr(provider_mod.httpx, "Client", FakeClient)

    prov_dir = tmp_path / "prov_out"
    prov_res = run_evaluation(
        execution_mode="real_model",
        output_dir=str(prov_dir),
        settings_override=Settings(
            LLM_PROVIDER="openai_compat",
            LLM_MODEL="mock-gpt",
            LLM_BASE_URL="http://localhost:8080/v1/chat/completions",
            LLM_API_KEY="mock-key",
            LLM_MAX_RETRIES=0,
        ),
    )
    assert prov_res["execution_metadata"]["execution_mode"] == "real_model"
    assert prov_res["execution_metadata"]["model"] == "mock-gpt"
    assert os.path.exists(prov_dir / "eval_provider_results.json")
    assert not os.path.exists(prov_dir / "eval_results.json")

    # 3. Missing key in real_model never silently falls back to replay
    fail_dir = tmp_path / "fail_out"
    fail_res = run_evaluation(
        execution_mode="real_model",
        output_dir=str(fail_dir),
        settings_override=Settings(LLM_API_KEY=""),
    )
    assert fail_res["counts"]["evaluated_cases"] == 0
    assert fail_res["counts"]["failed_cases"] > 0


def test_all_diagnostic_evidence_verbatim_integrity():
    import json
    import os
    from app.diagnostics import get_default_diagnostics
    from app.evidence import find_evidence_match

    responses_path = "data/responses.jsonl"
    assert os.path.exists(responses_path), "data/responses.jsonl must exist"

    with open(responses_path, "r", encoding="utf-8") as f:
        responses = {json.loads(line)["response_id"]: json.loads(line) for line in f}

    diagnostics = get_default_diagnostics()
    assert len(diagnostics) == 3, "Expected 3 default diagnostics"

    truncated_checked = False
    for d in diagnostics:
        for ev in d["evidence"]:
            rid = ev["response_id"]
            excerpt = ev["excerpt"]
            assert rid in responses, f"Response ID '{rid}' cited in diagnostic '{d['title']}' not found in dataset"
            source_text = responses[rid].get("answer_text", "")
            match = find_evidence_match(excerpt, source_text)
            assert match["valid"] is True, (
                f"Evidence excerpt in diagnostic '{d['title']}' failed validation for '{rid}': "
                f"{match.get('rejection_reason')}"
            )
            assert match["match_type"] == "exact"
            assert source_text[match["start_offset"]:match["end_offset"]] == excerpt

            if rid == "08f81acc-0824-4e3a-a5d5-58446e2a6a90":
                truncated_checked = True
                assert not excerpt.endswith('single "AI visibility'), "Excerpt must not be truncated mid-quote"
                assert excerpt.endswith('single "AI visibility score" at face value.')

    assert truncated_checked, "Expected diagnostic evidence for 08f81acc-0824-4e3a-a5d5-58446e2a6a90"

    # Also verify synced artifact final_report.json preserves complete quote and exact source match
    final_report_path = "evaluation/results/final_report.json"
    if os.path.exists(final_report_path):
        with open(final_report_path, "r", encoding="utf-8") as f:
            final_report = json.load(f)
        for d in final_report.get("diagnostics", []):
            for ev in d.get("evidence", []):
                rid = ev["response_id"]
                excerpt = ev["excerpt"]
                assert rid in responses
                source_text = responses[rid].get("answer_text", "")
                match = find_evidence_match(excerpt, source_text)
                assert match["valid"] is True and match["match_type"] == "exact"
                assert source_text[match["start_offset"]:match["end_offset"]] == excerpt
                if rid == "08f81acc-0824-4e3a-a5d5-58446e2a6a90":
                    assert excerpt.endswith('single "AI visibility score" at face value.')


