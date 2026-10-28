import os
import tempfile
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Dataset, Response as DBResponse, Citation as DBCitation
from app.ingestion import import_dataset


@pytest.fixture
def db_session():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    Session = sessionmaker(bind=test_engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_import_actual_dataset(db_session):
    res = import_dataset(db_session, "test-historical-dataset", "data")
    assert res.imported_prompts == 50
    assert res.imported_responses == 150
    assert res.imported_citations == 2439
    assert len(res.invalid_records) == 0
    assert res.validation_status == "valid"

    # Verify rows in DB
    db_resp_count = db_session.query(DBResponse).count()
    assert db_resp_count == 150
    db_cit_count = db_session.query(DBCitation).count()
    assert db_cit_count == 2439


def test_import_idempotent(db_session):
    # First import
    res1 = import_dataset(db_session, "idempotent-test", "data")
    assert res1.imported_responses == 150

    # Second import with same dataset name
    res2 = import_dataset(db_session, "idempotent-test", "data")
    assert res2.imported_responses == 150

    # Verify no duplicate responses created in DB
    assert db_session.query(DBResponse).count() == 150


def test_import_invalid_record_isolation(db_session):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create prompts.jsonl with 1 valid and 1 malformed record
        prompts_file = os.path.join(tmpdir, "prompts.jsonl")
        with open(prompts_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({"prompt_id": "p1", "run_id": "r1", "text": "Valid prompt"}) + "\n")
            f.write("MALFORMED JSON LINE\n")
            f.write(json.dumps({"prompt_id": "p2", "run_id": "r1", "text": ""}) + "\n")  # empty text

        # Create responses.jsonl with 1 valid, 1 invalid engine, 1 missing field
        resp_file = os.path.join(tmpdir, "responses.jsonl")
        with open(resp_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "response_id": "resp-valid",
                "run_id": "r1",
                "prompt_id": "p1",
                "engine": "chatgpt",
                "answer_text": "Good response",
                "capture_status": "captured"
            }) + "\n")
            f.write(json.dumps({
                "response_id": "resp-bad-engine",
                "run_id": "r1",
                "prompt_id": "p1",
                "engine": "unknown_ai_engine",
                "answer_text": "Bad engine response",
                "capture_status": "captured"
            }) + "\n")

        res = import_dataset(db_session, "isolation-test", tmpdir)

        # Valid prompt was imported
        assert res.imported_prompts == 1
        # Valid response was imported
        assert res.imported_responses == 1
        # Invalid records captured
        assert len(res.invalid_records) >= 2
        assert res.validation_status == "partial"

        # Check DB only contains the valid response
        responses = db_session.query(DBResponse).all()
        assert len(responses) == 1
        assert responses[0].source_response_id == "resp-valid"

