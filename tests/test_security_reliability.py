import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.ingestion import ImportLimitError, PathSecurityError, import_dataset, validate_safe_source_directory
from app.main import app
from app.models import AnalysisRun, Dataset, Report, Response as DBResponse, ResponseResult
from app.schemas import DatasetImportRequest


@pytest.fixture
def isolated_api(tmp_path, monkeypatch):
    db_file = tmp_path / "sec_test.db"
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    test_settings = Settings(
        APP_ENV="development",
        DATABASE_URL=f"sqlite:///{db_file}",
        ANALYST_TOKEN="analyst-one-secret",
        SECONDARY_ANALYST_TOKEN="analyst-two-secret",
        REVIEWER_TOKEN="reviewer-one-secret",
        ADMIN_TOKEN="admin-one-secret",
        ALLOWED_IMPORT_DIRS="data,fixtures",
        MAX_REQUEST_BODY_BYTES=1024 * 1024,
        MAX_IMPORT_FILE_BYTES=256 * 1024,
        MAX_IMPORT_RECORDS_PER_FILE=500,
    )

    def override_get_db():
        db = TestSession()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.auth.get_settings", lambda: test_settings)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, TestSession, test_settings
    finally:
        app.dependency_overrides.clear()


def test_path_traversal_and_sibling_prefix_bypass_blocked(tmp_path, monkeypatch):
    cwd = tmp_path / "workspace"
    allowed = cwd / "data"
    sibling_secret = cwd / "data_secret"
    allowed.mkdir(parents=True)
    sibling_secret.mkdir(parents=True)
    (sibling_secret / "responses.jsonl").write_text("{}", encoding="utf-8")

    monkeypatch.chdir(cwd)
    monkeypatch.setenv("ALLOWED_IMPORT_DIRS", "data")

    # Relative traversal, absolute paths, and null bytes must fail Pydantic validation
    for bad_path in ("../data", "data/../../secret", str(allowed), "data\x00/x", "app", "data_secret"):
        with pytest.raises(ValidationError):
            DatasetImportRequest(dataset_name="bad", source_directory=bad_path)

    # Service-layer boundary must also block sibling prefix bypass and directory escape
    with pytest.raises(PathSecurityError):
        validate_safe_source_directory("data_secret", allowed_roots=[allowed])
    with pytest.raises(PathSecurityError):
        validate_safe_source_directory("../workspace/data", allowed_roots=[allowed])

    assert validate_safe_source_directory("data", allowed_roots=[allowed]) == allowed.resolve()


def test_multipart_upload_validation_and_limits(isolated_api):
    client, _, test_settings = isolated_api
    a1_headers = {"Authorization": f"Bearer {test_settings.ANALYST_TOKEN}"}
    rev_headers = {"Authorization": f"Bearer {test_settings.REVIEWER_TOKEN}"}

    valid_prompts = json.dumps({"prompt_id": "p1", "run_id": "r1", "text": "Is Kasparro reliable?"}) + "\n"
    valid_responses = (
        json.dumps({
            "response_id": "resp-1",
            "run_id": "r1",
            "prompt_id": "p1",
            "engine": "chatgpt",
            "capture_status": "captured",
            "answer_text": "Kasparro is worth considering for AISO.",
        })
        + "\n"
    )

    # 1. Unauthenticated upload rejected
    r_unauth = client.post(
        "/datasets/upload",
        data={"dataset_name": "up-1"},
        files={"responses_file": ("responses.jsonl", valid_responses.encode(), "application/jsonl")},
    )
    assert r_unauth.status_code == 401

    # 2. Reviewer upload forbidden
    r_rev = client.post(
        "/datasets/upload",
        headers=rev_headers,
        data={"dataset_name": "up-1"},
        files={"responses_file": ("responses.jsonl", valid_responses.encode(), "application/jsonl")},
    )
    assert r_rev.status_code == 403

    # 3. Bad file extension & double extension rejected
    for bad_name in ("malware.exe", "payload.jsonl.exe", "../../escape.jsonl"):
        r_ext = client.post(
            "/datasets/upload",
            headers=a1_headers,
            data={"dataset_name": "up-bad"},
            files={"responses_file": (bad_name, valid_responses.encode(), "application/jsonl")},
        )
        assert r_ext.status_code == 400

    # 4. Disallowed MIME type rejected
    r_mime = client.post(
        "/datasets/upload",
        headers=a1_headers,
        data={"dataset_name": "up-mime"},
        files={"responses_file": ("responses.jsonl", valid_responses.encode(), "text/html")},
    )
    assert r_mime.status_code == 400

    # 5. Binary NUL byte content rejected
    r_bin = client.post(
        "/datasets/upload",
        headers=a1_headers,
        data={"dataset_name": "up-bin"},
        files={"responses_file": ("responses.jsonl", b"{\"x\":1}\x00\n", "application/jsonl")},
    )
    assert r_bin.status_code == 400

    # 6. Oversized upload rejected cleanly (HTTP 413)
    oversized = b"x" * (test_settings.MAX_IMPORT_FILE_BYTES + 128)
    r_big = client.post(
        "/datasets/upload",
        headers=a1_headers,
        data={"dataset_name": "up-big"},
        files={"responses_file": ("responses.jsonl", oversized, "application/jsonl")},
    )
    assert r_big.status_code == 413

    # 7. Clean upload succeeds and imports validated records
    r_ok = client.post(
        "/datasets/upload",
        headers=a1_headers,
        data={"dataset_name": "up-clean"},
        files={
            "prompts_file": ("prompts.jsonl", valid_prompts.encode(), "application/jsonl"),
            "responses_file": ("responses.jsonl", valid_responses.encode(), "application/jsonl"),
        },
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["imported_prompts"] == 1
    assert r_ok.json()["imported_responses"] == 1


def test_role_isolation_ownership_and_error_sanitization(isolated_api, monkeypatch):
    client, Session, test_settings = isolated_api
    a1_headers = {"Authorization": f"Bearer {test_settings.ANALYST_TOKEN}"}
    a2_headers = {"Authorization": f"Bearer {test_settings.SECONDARY_ANALYST_TOKEN}"}
    rev_headers = {"Authorization": f"Bearer {test_settings.REVIEWER_TOKEN}"}
    admin_headers = {"Authorization": f"Bearer {test_settings.ADMIN_TOKEN}"}

    valid_prompts = json.dumps({"prompt_id": "p1", "run_id": "r1", "text": "Does Kasparro work?"}) + "\n"
    valid_responses = (
        json.dumps({
            "response_id": "resp-own-1",
            "run_id": "r1",
            "prompt_id": "p1",
            "engine": "gemini",
            "capture_status": "captured",
            "answer_text": "Kasparro is worth considering.",
        })
        + "\n"
    )

    # Analyst 1 creates dataset, analysis, draft report
    ds1 = client.post(
        "/datasets/upload",
        headers=a1_headers,
        data={"dataset_name": "shared-name"},
        files={
            "prompts_file": ("prompts.jsonl", valid_prompts.encode(), "application/jsonl"),
            "responses_file": ("responses.jsonl", valid_responses.encode(), "application/jsonl"),
        },
    )
    assert ds1.status_code == 200
    ds1_id = ds1.json()["dataset_id"]

    # Analyst 2 using the SAME dataset_name receives their own isolated dataset ID
    ds2 = client.post(
        "/datasets/upload",
        headers=a2_headers,
        data={"dataset_name": "shared-name"},
        files={
            "prompts_file": ("prompts.jsonl", valid_prompts.encode(), "application/jsonl"),
            "responses_file": ("responses.jsonl", valid_responses.encode(), "application/jsonl"),
        },
    )
    assert ds2.status_code == 200
    ds2_id = ds2.json()["dataset_id"]
    assert ds2_id != ds1_id

    run1 = client.post("/analyses", headers=a1_headers, json={"dataset_id": ds1_id, "execution_mode": "replay"})
    assert run1.status_code == 200
    run1_id = run1.json()["analysis_id"]

    rep1 = client.post(f"/reports?dataset_id={ds1_id}&analysis_id={run1_id}", headers=a1_headers)
    assert rep1.status_code == 200
    rep1_id = rep1.json()["report_id"]
    v1_id = rep1.json()["current_draft_version_id"]

    # Analyst 2 isolation checks -> 403 Forbidden across all of Analyst 1's resources
    assert client.get(f"/datasets/{ds1_id}", headers=a2_headers).status_code == 403
    assert client.delete(f"/datasets/{ds1_id}", headers=a2_headers).status_code == 403
    assert client.post("/analyses", headers=a2_headers, json={"dataset_id": ds1_id, "execution_mode": "replay"}).status_code == 403
    assert client.get(f"/analyses/{run1_id}", headers=a2_headers).status_code == 403
    assert client.post(f"/reports?dataset_id={ds1_id}&analysis_id={run1_id}", headers=a2_headers).status_code == 403
    assert client.get(f"/reports/{rep1_id}", headers=a2_headers).status_code == 403
    assert client.patch(f"/reports/{rep1_id}", headers=a2_headers, json={"title": "Hijacked"}).status_code == 403
    assert client.post(f"/reports/{rep1_id}/submit", headers=a2_headers).status_code == 403
    assert client.get(f"/reports/{rep1_id}/export", headers=a2_headers).status_code == 403

    # Listing datasets isolates per analyst, while Admin sees both
    a1_list = [d["dataset_id"] for d in client.get("/datasets", headers=a1_headers).json()]
    assert a1_list == [ds1_id]
    admin_list = {d["dataset_id"] for d in client.get("/datasets", headers=admin_headers).json()}
    assert {ds1_id, ds2_id}.issubset(admin_list)

    # Admin isolation: Admin cannot act as Analyst or Reviewer
    assert client.post("/datasets", headers=admin_headers, json={"dataset_name": "x", "source_directory": "data"}).status_code == 403
    assert client.post(
        f"/reports/{rep1_id}/decision",
        headers=admin_headers,
        json={"version_id": v1_id, "decision": "approve", "comment": "Admin bypass"},
    ).status_code == 403
    # Reviewer cannot delete datasets or read analyst dataset list
    assert client.get("/datasets", headers=rev_headers).status_code == 403
    assert client.delete(f"/datasets/{ds1_id}", headers=rev_headers).status_code == 403

    # Admin CAN delete dataset cleanly
    assert client.delete(f"/datasets/{ds2_id}", headers=admin_headers).status_code == 200

    # Non-dev environment rejects default dev bearer tokens
    prod_settings = Settings(APP_ENV="production")
    monkeypatch.setattr("app.auth.get_settings", lambda: prod_settings)
    app.dependency_overrides[get_settings] = lambda: prod_settings
    r_prod = client.get("/datasets", headers={"Authorization": "Bearer dev-analyst-token-2026"})
    assert r_prod.status_code == 401
    app.dependency_overrides[get_settings] = lambda: test_settings
    monkeypatch.setattr("app.auth.get_settings", lambda: test_settings)

    # Error handling hides internal paths / stack details
    r_missing = client.post("/analyses", headers=a1_headers, json={"dataset_id": "nonexistent-ds", "execution_mode": "replay"})
    assert r_missing.status_code == 404

    def boom_execute(*args, **kwargs):
        raise RuntimeError("psycopg2 error at C:\\internal\\secret\\db.sqlite")

    monkeypatch.setattr("app.main.execute_analysis", boom_execute)
    r_err = client.post("/analyses", headers=a1_headers, json={"dataset_id": ds1_id, "execution_mode": "replay"})
    assert r_err.status_code == 500
    assert r_err.json()["detail"] == "Analysis execution failed"
    assert "secret" not in r_err.text and "C:\\" not in r_err.text


def test_import_duplicates_limits_and_database_rollback(tmp_path):
    db_file = tmp_path / "rollback_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 1. Duplicate in-file IDs and orphaned prompt_id flagged cleanly
        dup_dir = tmp_path / "dup_ds"
        dup_dir.mkdir()
        (dup_dir / "prompts.jsonl").write_text(
            "\n".join([
                json.dumps({"prompt_id": "p1", "run_id": "r1", "text": "Valid prompt"}),
                json.dumps({"prompt_id": "p1", "run_id": "r1", "text": "Duplicate prompt"}),
            ]),
            encoding="utf-8",
        )
        (dup_dir / "responses.jsonl").write_text(
            "\n".join([
                json.dumps({"response_id": "resp-1", "run_id": "r1", "prompt_id": "p1", "engine": "chatgpt", "capture_status": "captured", "answer_text": "Kasparro works."}),
                json.dumps({"response_id": "resp-1", "run_id": "r1", "prompt_id": "p1", "engine": "chatgpt", "capture_status": "captured", "answer_text": "Duplicate response."}),
                json.dumps({"response_id": "resp-orphan", "run_id": "r1", "prompt_id": "p-missing", "engine": "chatgpt", "capture_status": "captured", "answer_text": "Orphan response."}),
            ]),
            encoding="utf-8",
        )
        res = import_dataset(db, dataset_name="dup-check", source_directory=str(dup_dir))
        assert res.validation_status == "partial"
        assert res.imported_prompts == 1
        assert res.imported_responses == 1
        reasons = [inv.reason.lower() for inv in res.invalid_records]
        assert any("duplicate prompt_id" in r for r in reasons)
        assert any("duplicate response_id" in r for r in reasons)
        assert any("not found in valid prompts" in r for r in reasons)

        # 2. Mid-transaction rollback on failure inside import_dataset
        db2 = Session()
        fail_dir = tmp_path / "rollback_ds"
        fail_dir.mkdir()
        (fail_dir / "prompts.jsonl").write_text(
            json.dumps({"prompt_id": "px", "run_id": "rx", "text": "Prompt X"}) + "\n",
            encoding="utf-8",
        )
        (fail_dir / "responses.jsonl").write_text(
            json.dumps({"response_id": "respx", "run_id": "rx", "prompt_id": "px", "engine": "gemini", "capture_status": "captured", "answer_text": "Kasparro response"}) + "\n",
            encoding="utf-8",
        )
        # Exceed max_records_per_file in citations AFTER Dataset & Response rows were flushed!
        (fail_dir / "citations.jsonl").write_text(
            "\n".join(
                json.dumps({
                    "citation_id": f"c{i}",
                    "response_id": "respx",
                    "prompt_id": "px",
                    "engine": "gemini",
                    "order": i + 1,
                    "citation_type": "sources_panel",
                    "url": "https://example.com",
                })
                for i in range(5)
            ),
            encoding="utf-8",
        )
        before_ds_count = db2.query(Dataset).count()
        before_resp_count = db2.query(DBResponse).count()
        with pytest.raises(ImportLimitError):
            import_dataset(db2, dataset_name="should-rollback", source_directory=str(fail_dir), max_records_per_file=2)

        assert db2.query(Dataset).count() == before_ds_count
        assert db2.query(DBResponse).count() == before_resp_count
        assert db2.query(Dataset).filter(Dataset.name == "should-rollback").first() is None
        db2.close()
    finally:
        db.close()




def test_import_field_types_and_length_limits(tmp_path):
    from app.ingestion import validate_prompt_record, validate_response_record, validate_citation_record

    assert validate_prompt_record({"prompt_id": "p1", "run_id": 7, "text": "Prompt"})[0] is False
    assert validate_prompt_record({"prompt_id": "p" * 129, "run_id": "r1", "text": "Prompt"})[0] is False
    assert validate_prompt_record({"prompt_id": "p1", "run_id": "r1", "text": "Prompt"})[0] is True

    valid_response = {
        "response_id": "r1", "run_id": "run1", "prompt_id": "p1",
        "engine": "chatgpt", "answer_text": "A response",
        "capture_status": "captured",
    }
    assert validate_response_record({**valid_response, "run_id": None})[0] is False
    assert validate_response_record({**valid_response, "answer_text": "x" * 200001})[0] is False
    assert validate_response_record(valid_response)[0] is True

    valid_citation = {
        "citation_id": "c1", "response_id": "r1", "prompt_id": "p1",
        "engine": "chatgpt", "order": 1, "citation_type": "sources_panel",
        "url": "https://example.com",
    }
    assert validate_citation_record({**valid_citation, "url": "file:///etc/passwd"})[0] is False
    assert validate_citation_record({**valid_citation, "prompt_id": 9})[0] is False
    assert validate_citation_record(valid_citation)[0] is True


def test_request_size_limit_without_content_length(monkeypatch):
    import asyncio
    from starlette.requests import Request
    from app.main import enforce_request_size_limit

    settings = Settings(MAX_REQUEST_BODY_BYTES=10)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    async def receive():
        return {"type": "http.request", "body": b"x" * 11, "more_body": False}

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/test",
        "raw_path": b"/test", "query_string": b"", "headers": [],
        "client": ("testclient", 123), "server": ("testserver", 80),
    }
    request = Request(scope, receive=receive)

    async def call_next(_request):
        pytest.fail("Oversized body must be rejected before reaching the route")

    response = asyncio.run(enforce_request_size_limit(request, call_next))
    assert response.status_code == 413


def test_request_size_limit_rejects_content_length_mismatch(monkeypatch):
    import asyncio
    from starlette.requests import Request
    from app.main import enforce_request_size_limit

    settings = Settings(MAX_REQUEST_BODY_BYTES=100)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)

    async def receive():
        return {"type": "http.request", "body": b"actual-body", "more_body": False}

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/test",
        "raw_path": b"/test", "query_string": b"", "headers": [(b"content-length", b"1")],
        "client": ("testclient", 123), "server": ("testserver", 80),
    }
    request = Request(scope, receive=receive)

    async def call_next(_request):
        pytest.fail("Mismatched body length must be rejected before reaching the route")

    response = asyncio.run(enforce_request_size_limit(request, call_next))
    assert response.status_code == 400


def test_multipart_duplicate_fields_are_rejected(isolated_api):
    client, _, settings = isolated_api
    boundary = "security-boundary"
    valid_line = json.dumps({
        "response_id": "duplicate-test", "run_id": "run-1", "prompt_id": "prompt-1",
        "engine": "chatgpt", "capture_status": "captured", "answer_text": "Kasparro is mentioned.",
    })
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"dataset_name\"\r\n\r\nsecurity-test\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"responses_file\"; filename=\"responses.jsonl\"\r\nContent-Type: application/jsonl\r\n\r\n{valid_line}\r\n",
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"responses_file\"; filename=\"responses.jsonl\"\r\nContent-Type: application/jsonl\r\n\r\n{valid_line}\r\n",
        f"--{boundary}--\r\n",
    ]
    response = client.post(
        "/datasets/upload",
        headers={
            "Authorization": f"Bearer {settings.ANALYST_TOKEN}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        content="".join(parts).encode("utf-8"),
    )
    assert response.status_code == 400
    assert "Duplicate multipart field" in response.text


def test_held_out_benchmark_is_disjoint_from_regression_set():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    def load(path):
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    regression = load(root / "evaluation" / "cases.jsonl")
    held_out = load(root / "evaluation" / "held_out_cases.jsonl")
    regression_prompts = {case["prompt_id"] for case in regression}
    held_out_prompts = {case["prompt_id"] for case in held_out}
    assert len(held_out) >= 30
    assert not regression_prompts.intersection(held_out_prompts)
    assert len({case["case_id"] for case in held_out}) == len(held_out)
    assert all(case["source_type"] == "held_out_synthetic" for case in held_out)
    assert all(case["annotation_status"] == "provisional_single_annotator" for case in held_out)
    assert all(set(case["expected"]) == {
        "kasparro_mentioned", "kasparro_recommended", "kasparro_negative"
    } for case in held_out)



def test_import_directory_rejects_symlinked_dataset_file(tmp_path, monkeypatch):
    allowed_root = tmp_path / "imports"
    dataset_dir = allowed_root / "dataset"
    outside_dir = tmp_path / "outside"
    dataset_dir.mkdir(parents=True)
    outside_dir.mkdir()
    outside_file = outside_dir / "responses.jsonl"
    outside_file.write_text('{"sensitive":"outside"}\n', encoding="utf-8")
    try:
        (dataset_dir / "responses.jsonl").symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not permitted on this platform")

    monkeypatch.chdir(tmp_path)
    with pytest.raises(PathSecurityError):
        validate_safe_source_directory("imports/dataset", allowed_roots=[allowed_root])


def test_multipart_invalid_utf8_form_field_is_rejected(isolated_api):
    client, _, settings = isolated_api
    boundary = "invalid-utf8-boundary"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"dataset_name\"\r\n\r\n".encode("ascii")
        + b"\xff\xfe"
        + f"\r\n--{boundary}--\r\n".encode("ascii")
    )
    response = client.post(
        "/datasets/upload",
        headers={
            "Authorization": f"Bearer {settings.ANALYST_TOKEN}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        content=body,
    )
    assert response.status_code == 400
    assert "valid UTF-8" in response.text
