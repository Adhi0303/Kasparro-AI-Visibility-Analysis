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

        assert accepted[1]["excerpt"] == "Kasparro provides\nstructured scoring"
        assert accepted[1]["submitted_excerpt"] == normalized_quote
        assert accepted[1]["match_type"] == "normalized_whitespace"
        assert accepted[1]["validation_status"] == "valid"
        assert answer_text[accepted[1]["start_offset"]:accepted[1]["end_offset"]] == "Kasparro provides\nstructured scoring"

        accepted_excerpts = [item["excerpt"] for item in accepted]
        assert fabricated_quote not in accepted_excerpts
        assert "   " not in accepted_excerpts

        labels = json.loads(row.labels_json)
        assert labels["evidence"] == accepted
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




def test_unvalidated_evidence_leakage_and_unsupported_location_rejected(monkeypatch):
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
        ds = Dataset(name="leakage-guard-test", source_hash="hash_lg", validation_status="valid")
        db.add(ds)
        db.flush()

        ans = "Kasparro is a solid option for mid-market teams."
        db_resp = DBResponse(
            dataset_id=ds.id,
            source_response_id="resp-loc-001",
            prompt_id="prompt-loc-001",
            engine="gemini",
            raw_payload=json.dumps({
                "response_id": "resp-loc-001",
                "prompt_id": "prompt-loc-001",
                "prompt_text": "Is Kasparro good?",
                "engine": "gemini",
                "answer_text": ans,
            }),
        )
        db.add(db_resp)
        db.commit()

        class LocStubClassifier(LLMBase):
            def classify(self, response_id, engine, answer_text, failure_scenario=None, prompt_text=None):
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
                        EvidenceItem(excerpt="Kasparro is a solid option", location="answer_text"),
                        EvidenceItem(excerpt="Kasparro is a solid option", location="user_prompt"),
                        EvidenceItem(excerpt="Kasparro is a solid option", location=""),
                        EvidenceItem(excerpt="Fabricated quote never written", location="answer_text"),
                    ],
                    confidence=0.9,
                    execution_mode="replay",
                    classifier_version="v1",
                )

        monkeypatch.setattr("app.classification.get_classifier", lambda **kwargs: LocStubClassifier())

        analysis = execute_analysis(db, dataset_id=ds.id, execution_mode="replay")
        row = db.query(ResponseResult).filter(ResponseResult.analysis_id == analysis.id).first()
        assert row is not None

        accepted = json.loads(row.evidence_json)
        labels = json.loads(row.labels_json)

        # Canonical evidence_json and labels["evidence"] must match identically with zero unvalidated leaks
        assert len(accepted) == 1
        assert labels["evidence"] == accepted
        assert accepted[0]["location"] == "answer_text"

        audit = labels["evidence_validation"]
        assert audit["accepted_count"] == 1
        assert audit["rejected_count"] == 3
        reasons = [r["rejection_reason"].lower() for r in audit["rejected"]]
        assert any("unsupported evidence location" in r and "user_prompt" in r for r in reasons)
        assert any("unsupported evidence location" in r for r in reasons)
        assert any("not found" in r for r in reasons)
        assert all(r["location"] != "answer_text" or r["excerpt"] == "Fabricated quote never written" for r in audit["rejected"])
    finally:
        db.close()


def test_replay_complete_sentence_and_bounded_clause_extraction():
    from app.llm.replay import ReplayClassifier
    from app.evidence import find_evidence_match

    clf = ReplayClassifier()

    # Long compound sentence (>360 chars) with complete punctuation-bounded clause on Kasparro
    long_compound = (
        "When B2B marketing leaders evaluate generative search platforms across multiple model vendors and regional markets "
        "while balancing enterprise procurement workflows, compliance checks, automated prompt libraries, and multi-workspace analytics, "
        "Kasparro is worth evaluating for agile AISO tracking, "
        "whereas larger enterprise procurement teams frequently benchmark historical governance modules and custom data warehouse exports across multiple continents before signing contracts."
    )
    assert len(long_compound) > 360
    res = clf.classify("resp-long-clause", "chatgpt", long_compound)
    assert res.status == "success"
    assert len(res.evidence) == 1
    ev_text = res.evidence[0].excerpt
    assert len(ev_text) <= 360
    assert ev_text.endswith(",")
    assert "Kasparro is worth evaluating for agile AISO tracking" in ev_text
    assert find_evidence_match(ev_text, long_compound)["valid"] is True

    # Unbounded run-on > 360 chars with NO internal punctuation skip cleanly rather than blind slicing
    run_on = "In a very dense paragraph without separators " + ("token " * 55) + "Kasparro remains discussed continuously without any commas or stops anywhere in this excessively extended span"
    assert len(run_on) > 360
    res_runon = clf.classify("resp-runon", "gemini", run_on)
    assert res_runon.status == "success"
    assert res_runon.evidence == []
    assert any("exceeds" in item["reason"].lower() for item in clf.last_extraction_skips)


def test_downstream_report_validation_markdown_html_and_missing_sources():
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.evidence import render_report_html, render_report_markdown, validate_report_evidence
    from app.export import export_approved_report
    from app.models import Dataset, Response as DBResponse, ResponseResult, AnalysisRun
    from app.reports import create_initial_report, edit_draft_report, submit_report_for_review
    from app.review import process_review_decision
    from app.schemas import DiagnosticItem, DraftReportEditRequest, ReviewDecisionRequest

    source_lookup = {
        "r-ok": {"answer_text": "Kasparro is worth considering for B2B SaaS workflows."},
    }
    raw_diags = [
        {
            "title": "Finding 1",
            "observed_pattern": "Pattern",
            "comparison": "Comp",
            "evidence": [
                {"response_id": "r-ok", "engine": "chatgpt", "prompt": "p1", "excerpt": "Kasparro is worth considering"},
                {"response_id": "r-ok", "engine": "chatgpt", "prompt": "p1", "excerpt": "Totally invented claim"},
                {"response_id": "r-missing", "engine": "gemini", "prompt": "p2", "excerpt": "Missing response text"},
            ],
            "possible_explanation": "Exp",
            "validation_needed": "Val",
            "confidence_and_limitations": "Conf",
        }
    ]

    sanitized, audit = validate_report_evidence(raw_diags, source_lookup)
    assert len(sanitized[0]["evidence"]) == 1
    assert sanitized[0]["evidence"][0]["start_offset"] == 0
    assert audit["accepted_count"] == 1
    assert audit["rejected_count"] == 2
    assert any("missing" in r["rejection_reason"].lower() for r in audit["rejected"])

    # Full DB report lifecycle: edit with XSS & invalid evidence -> approve -> export JSON / Markdown / HTML
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        ds = Dataset(name="downstream-report-ds", source_hash="hash_ds_rep", validation_status="valid")
        db.add(ds)
        db.flush()

        r1_text = "However, Kasparro lacks independent validation and independent reviews."
        r2_text = "If you mean Kasparro (not Kaspr), there isn't enough public pricing info."
        for rid, pid, eng, txt in [
            ("resp-r1", "kasparro:ai_shortlisting:001", "chatgpt", r1_text),
            ("resp-r2", "kasparro:ai_shortlisting:018", "chatgpt", r2_text),
        ]:
            db.add(DBResponse(
                dataset_id=ds.id,
                source_response_id=rid,
                prompt_id=pid,
                engine=eng,
                raw_payload=json.dumps({
                    "response_id": rid,
                    "prompt_id": pid,
                    "prompt_text": "Does Kasparro work?",
                    "engine": eng,
                    "answer_text": txt,
                }),
            ))
        db.commit()

        from app.classification import execute_analysis
        analysis = execute_analysis(db, dataset_id=ds.id, execution_mode="replay")
        report = create_initial_report(db, dataset_id=ds.id, analysis_id=analysis.id)

        # Edit draft attempting to inject XSS in title and fabricated evidence excerpt
        edit_req = DraftReportEditRequest(
            title='Snapshot <script>alert("xss")</script>',
            diagnostics=[
                DiagnosticItem(
                    title='Unsafe <b>Tag</b>',
                    observed_pattern="Negative rate observed",
                    comparison="Comparison",
                    evidence=[
                        {
                            "response_id": "resp-r1",
                            "engine": "chatgpt",
                            "prompt": "p1",
                            "excerpt": "Kasparro lacks independent validation",
                        },
                        {
                            "response_id": "resp-r1",
                            "engine": "chatgpt",
                            "prompt": "p1",
                            "excerpt": "Fabricated quote <img src=x onerror=alert(1)>",
                        },
                    ],
                    possible_explanation="Exp",
                    validation_needed="Val",
                    confidence_and_limitations="Conf",
                )
            ],
        )
        draft_v2 = edit_draft_report(db, report.id, edit_req)
        draft_content = json.loads(draft_v2.content_json)
        assert len(draft_content["diagnostics"][0]["evidence"]) == 1
        assert draft_content["evidence_validation"]["rejected_count"] == 1

        submitted_v2 = submit_report_for_review(db, report.id)
        process_review_decision(
            db,
            report.id,
            ReviewDecisionRequest(version_id=submitted_v2.id, decision="approve", comment="Verified"),
        )

        exported_json = export_approved_report(db, report.id, output_format="json")
        assert len(exported_json["content"]["diagnostics"][0]["evidence"]) == 1

        exported_md = export_approved_report(db, report.id, output_format="markdown")
        assert "Kasparro lacks independent validation" in exported_md["rendered"]
        assert "Fabricated quote" not in exported_md["rendered"]

        exported_html = export_approved_report(db, report.id, output_format="html")
        html_out = exported_html["rendered"]
        assert "<script>" not in html_out
        assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;" in html_out
        assert "&lt;b&gt;Tag&lt;/b&gt;" in html_out
    finally:
        db.close()


def test_module2_prompt_context_and_category_aggregates(tmp_path):
    import json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.ingestion import import_dataset
    from app.classification import execute_analysis, get_analysis_status
    from app.llm.replay import ReplayClassifier

    clf = ReplayClassifier()

    # Literal repetition of prompt_text without new evaluation -> absent / False
    prompt_q = "Is Kasparro worth considering for B2B SaaS?"
    ans_echo = "Is Kasparro worth considering for B2B SaaS?\n\nTop alternatives in this category are Profound and Peec AI."
    res_echo = clf.classify("r-echo", "chatgpt", ans_echo, prompt_text=prompt_q)
    assert res_echo.kasparro_mentioned is False
    assert res_echo.kasparro_absent is True

    # Prompt repetition followed by genuine evaluation -> True + Recommended
    ans_recap_then_eval = (
        "You asked whether Kasparro is worth considering for B2B SaaS.\n"
        "Kasparro is well suited for mid-market B2B SaaS teams seeking AISO tracking."
    )
    res_eval = clf.classify("r-eval", "chatgpt", ans_recap_then_eval, prompt_text=prompt_q)
    assert res_eval.kasparro_mentioned is True
    assert res_eval.kasparro_recommended is True
    assert res_eval.kasparro_negative is False

    # Indirect question framing in the same sentence as genuine evaluation
    ans_mixed_sentence = (
        "You asked whether Kasparro is reliable, and third-party pilots show Kasparro is worth shortlisting."
    )
    res_mixed = clf.classify("r-mixed", "gemini", ans_mixed_sentence, prompt_text=prompt_q)
    assert res_mixed.kasparro_mentioned is True
    assert res_mixed.kasparro_recommended is True

    # Verify ingestion persists prompt_text -> category_aggregates populates multiple categories
    ds_dir = tmp_path / "mini_ds"
    ds_dir.mkdir()
    (ds_dir / "prompts.jsonl").write_text(
        "\n".join([
            json.dumps({"prompt_id": "p-trust", "run_id": "run-1", "text": "Is Kasparro legit and trustworthy or just a gimmick?"}),
            json.dumps({"prompt_id": "p-pricing", "run_id": "run-1", "text": "What is the cost and price for Kasparro setup and onboarding?"}),
        ]),
        encoding="utf-8",
    )
    (ds_dir / "responses.jsonl").write_text(
        "\n".join([
            json.dumps({"response_id": "r1", "run_id": "run-1", "prompt_id": "p-trust", "engine": "chatgpt", "capture_status": "captured", "answer_text": "Kasparro is not a scam and works well."}),
            json.dumps({"response_id": "r2", "run_id": "run-1", "prompt_id": "p-pricing", "engine": "gemini", "capture_status": "captured", "answer_text": "Kasparro offers transparent pricing for SMB teams."}),
        ]),
        encoding="utf-8",
    )
    (ds_dir / "citations.jsonl").write_text("", encoding="utf-8")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        ds_res = import_dataset(db, dataset_name="cat-test", source_directory=str(ds_dir))
        assert ds_res.imported_responses == 2
        run = execute_analysis(db, dataset_id=ds_res.dataset_id, execution_mode="replay")
        status_data = get_analysis_status(db, run.id)
        assert status_data.category_aggregates["trust_and_legitimacy"]["total_eligible"] == 1
        assert status_data.category_aggregates["pricing_and_implementation"]["total_eligible"] == 1
    finally:
        db.close()


@pytest.mark.parametrize(
    "text,exp_mentioned,exp_recommended,exp_negative",
    [
        # Passive & endorsement recommendations
        ("Kasparro is highly recommended by AISO practitioners.", True, True, False),
        ("Industry analysts endorse Kasparro for B2B SaaS AI visibility.", True, True, False),
        ("Kasparro is one of the best tools I recommend.", True, True, False),
        ("Kasparro is better suited for smaller B2B SaaS teams than enterprise suites.", True, True, False),
        ("Kasparro is a good fit for mid-market teams starting AISO.", True, True, False),
        ("Kasparro may be worth considering if you want lightweight AI monitoring.", True, True, False),
        # Competitor-only recommendation vs Kasparro neutral mention
        ("For enterprise AI visibility, Profound and BrightEdge are recommended, while Kasparro only provides basic monitoring.", True, False, False),
        ("Getting recommended by ChatGPT requires citations, and Kasparro tracks that metric.", True, False, False),
        ("I would not recommend Kasparro due to limited enterprise features.", True, False, True),
        # Negated negative allegations & double negation
        ("Kasparro is not unreliable.", True, False, False),
        ("Kasparro is not a scam.", True, False, False),
        ("There is no evidence that Kasparro is unreliable.", True, False, False),
        ("It would be unfair to describe Kasparro as untrustworthy.", True, False, False),
        # Neutral uncertainty vs negative claim
        ("There isn't enough public information to evaluate Kasparro.", True, False, False),
        ("Kasparro lacks independent validation.", True, False, True),
        # Coexisting recommendation and limitation
        ("Kasparro lacks independent case studies, though it is worth evaluating for early teams.", True, True, True),
        # Competitor negativity isolation
        ("BrightEdge has mixed reviews for SMBs, whereas Kasparro focuses on lightweight AISO.", True, False, False),
        # Pronoun & subject-shift ambiguity protection
        ("Kasparro competes with Profound. It is a strong option for enterprise SEO teams.", True, False, False),
        ("Kasparro offers monitoring tools. Profound has stronger enterprise reporting. It is widely recommended by large agencies.", True, False, False),
        ("Kasparro differs from BrightEdge. Their enterprise suite is widely recommended.", True, False, False),
        ("Kasparro is an early AISO tracker.\n\nProfound and BrightEdge lead the market. They are strongly recommended.", True, False, False),
        ("1. **Kasparro**: Niche tracker.\n2. **AthenaHQ**: Strongly recommended for enterprise teams. It is a top choice.", True, False, False),
        # Unambiguous single-brand continuation
        ("Kasparro is an AISO platform. It is well suited for agile SaaS teams and worth considering.", True, True, False),
    ],
)
def test_module2_recommendation_negation_and_pronoun_precision(
    text, exp_mentioned, exp_recommended, exp_negative
):
    from app.llm.replay import ReplayClassifier

    clf = ReplayClassifier()
    res = clf.classify("m2-case", "chatgpt", text)
    assert res.status == "success"
    assert res.kasparro_mentioned is exp_mentioned, f"Mention mismatch for: {text}"
    assert res.kasparro_recommended is exp_recommended, f"Recommended mismatch for: {text}"
    assert res.kasparro_negative is exp_negative, f"Negative mismatch for: {text}"


def test_module2_long_multi_opinion_response_end_to_end():
    from app.llm.replay import ReplayClassifier
    from app.evidence import find_evidence_match

    clf = ReplayClassifier()
    prompt_q = "Compare Kasparro and Profound for B2B SaaS AI search monitoring."
    answer = (
        "Compare Kasparro and Profound for B2B SaaS AI search monitoring.\n\n"
        "Kasparro competes with Profound in the emerging AISO monitoring segment. It is a strong option for multi-team Fortune 500 enterprises, "
        "though Profound currently captures most Fortune 500 budgets.\n\n"
        "However, Kasparro is better suited for smaller B2B SaaS teams that want practical citation tracking without complex setup. "
        "While Kasparro is not a scam, it still lacks independent validation and third-party case studies."
    )
    res = clf.classify("resp-multi-opinion", "chatgpt", answer, prompt_text=prompt_q)
    assert res.kasparro_mentioned is True
    assert res.kasparro_recommended is True
    assert res.kasparro_negative is True
    assert "profound" in res.competitors
    assert len(res.evidence) >= 1
    for ev in res.evidence:
        match = find_evidence_match(ev.excerpt, answer, location=ev.location)
        assert match["valid"] is True
        assert answer[match["start_offset"]:match["end_offset"]] == match["canonical_excerpt"]



def test_provider_rejects_inconsistent_classification_labels():
    import pytest
    from pydantic import ValidationError
    from app.llm.provider import ProviderClassificationOutput

    valid = {
        "kasparro_absent": False,
        "kasparro_mentioned": True,
        "kasparro_recommended": True,
        "kasparro_negative": False,
        "competitors": [],
        "recommendation_position": 1,
        "evidence": [{"excerpt": "Kasparro is recommended", "location": "answer_text"}],
        "confidence": 0.9,
    }
    assert ProviderClassificationOutput.model_validate(valid).kasparro_mentioned is True

    invalid_cases = [
        {**valid, "kasparro_absent": True},
        {**valid, "kasparro_mentioned": False},
        {**valid, "kasparro_recommended": True, "kasparro_mentioned": False, "kasparro_absent": True},
        {**valid, "kasparro_negative": True, "kasparro_mentioned": False, "kasparro_absent": True},
        {**valid, "kasparro_recommended": False, "recommendation_position": 1},
        {**valid, "evidence": [{"excerpt": "quote", "location": "user_prompt"}]},
        {**valid, "evidence": [{"excerpt": ""}]},
    ]
    for payload in invalid_cases:
        with pytest.raises(ValidationError):
            ProviderClassificationOutput.model_validate(payload)


def test_provider_retries_transient_http_errors_with_bounded_delay(monkeypatch):
    import json
    import app.llm.provider as provider_mod
    from app.config import Settings
    from app.llm.provider import ProviderClassifier

    calls = []
    delays = []

    class FakeResponse:
        def __init__(self, status_code, body, headers=None):
            self.status_code = status_code
            self._body = body
            self.headers = headers or {}
            self.text = json.dumps(body)

        def json(self):
            return self._body

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return FakeResponse(429, {"error": "rate limited"}, {"Retry-After": "0"})
            payload = {
                "kasparro_absent": False,
                "kasparro_mentioned": True,
                "kasparro_recommended": False,
                "kasparro_negative": False,
                "competitors": [],
                "recommendation_position": None,
                "evidence": [],
                "confidence": 0.8,
            }
            return FakeResponse(200, {"choices": [{"message": {"content": json.dumps(payload)}}]})

    monkeypatch.setattr(provider_mod.httpx, "Client", FakeClient)
    monkeypatch.setattr(provider_mod.time, "sleep", lambda delay: delays.append(delay))
    classifier = ProviderClassifier(
        Settings(LLM_API_KEY="test-key", LLM_MAX_RETRIES=1)
    )
    result = classifier.classify("retry-case", "chatgpt", "Kasparro is mentioned.")
    assert result.status == "success"
    assert len(calls) == 2
    assert delays == [0.0]


def test_provider_does_not_retry_permanent_http_errors(monkeypatch):
    import app.llm.provider as provider_mod
    from app.config import Settings
    from app.llm.provider import ProviderClassifier

    calls = []

    class FakeResponse:
        status_code = 401
        headers = {}
        text = "unauthorized"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, *args, **kwargs):
            calls.append(1)
            return FakeResponse()

    monkeypatch.setattr(provider_mod.httpx, "Client", FakeClient)
    classifier = ProviderClassifier(Settings(LLM_API_KEY="test-key", LLM_MAX_RETRIES=3))
    result = classifier.classify("permanent-error", "chatgpt", "Kasparro is mentioned.")
    assert result.status == "failed"
    assert len(calls) == 1
    assert "401" in result.failure_reason



def test_evaluation_grader_reports_specificity_accuracy_and_support():
    import pytest
    from evaluation.grader import compute_label_metrics, grade_predictions

    metrics = compute_label_metrics(
        [True, True, False, False],
        [True, False, True, False],
    )
    assert metrics["support"] == 4
    assert metrics["positive_support"] == 2
    assert metrics["negative_support"] == 2
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["true_negatives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["specificity"] == 0.5
    assert metrics["accuracy"] == 0.5
    assert metrics["balanced_accuracy"] == 0.5

    with pytest.raises(ValueError):
        compute_label_metrics([True], [])
    with pytest.raises(TypeError):
        compute_label_metrics([1], [True])
    with pytest.raises(ValueError):
        grade_predictions([{"kasparro_mentioned": True}], [])
