import os
import json
import hashlib
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Dataset, Response as DBResponse, Citation as DBCitation
from app.schemas import DatasetImportResponse, InvalidRecordInfo


VALID_ENGINES = {"aimode", "chatgpt", "gemini"}
VALID_CITATION_TYPES = {"inline_hyperlink", "sources_panel"}


def compute_directory_hash(directory_path: str) -> str:
    """Computes a combined SHA-256 hash of all .jsonl files in the directory."""
    hasher = hashlib.sha256()
    target_files = ["prompts.jsonl", "responses.jsonl", "citations.jsonl"]
    for filename in sorted(target_files):
        filepath = os.path.join(directory_path, filename)
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
    return hasher.hexdigest()


def validate_prompt_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(record, dict):
        return False, "Record is not a valid JSON object"
    for field in ("prompt_id", "run_id", "text"):
        if field not in record or record[field] is None:
            return False, f"Missing required prompt field: {field}"
    if not str(record["text"]).strip():
        return False, "Prompt text cannot be empty"
    return True, None


def validate_response_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(record, dict):
        return False, "Record is not a valid JSON object"
    for field in ("response_id", "run_id", "prompt_id", "engine", "answer_text", "capture_status"):
        if field not in record or record[field] is None:
            return False, f"Missing required response field: {field}"
    if record["engine"] not in VALID_ENGINES:
        return False, f"Invalid engine: {record['engine']}. Must be one of {VALID_ENGINES}"
    if record["capture_status"] != "captured":
        return False, f"Invalid capture_status: {record['capture_status']}. Must be 'captured'"
    if not str(record["answer_text"]).strip():
        return False, "answer_text cannot be empty"
    return True, None


def validate_citation_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(record, dict):
        return False, "Record is not a valid JSON object"
    for field in ("citation_id", "response_id", "prompt_id", "engine", "order", "citation_type", "url"):
        if field not in record or record[field] is None:
            return False, f"Missing required citation field: {field}"
    if record["engine"] not in VALID_ENGINES:
        return False, f"Invalid engine: {record['engine']}"
    if record["citation_type"] not in VALID_CITATION_TYPES:
        return False, f"Invalid citation_type: {record['citation_type']}"
    if not isinstance(record["order"], int) or record["order"] < 1:
        return False, f"Order must be an integer >= 1"
    if not str(record["url"]).strip():
        return False, "Citation URL cannot be empty"
    return True, None


def import_dataset(db: Session, dataset_name: str, source_directory: str) -> DatasetImportResponse:
    if not os.path.exists(source_directory):
        raise FileNotFoundError(f"Source directory '{source_directory}' does not exist")

    source_hash = compute_directory_hash(source_directory)

    # Check for existing dataset with same name & hash, or create new
    dataset = db.query(Dataset).filter(Dataset.name == dataset_name).first()
    if not dataset:
        dataset = Dataset(
            name=dataset_name,
            source_hash=source_hash,
            validation_status="valid"
        )
        db.add(dataset)
        db.flush()

    invalid_records: List[InvalidRecordInfo] = []

    # 1. Prompts
    prompts_path = os.path.join(source_directory, "prompts.jsonl")
    valid_prompt_count = 0
    valid_prompt_ids = set()

    if os.path.exists(prompts_path):
        with open(prompts_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    is_valid, reason = validate_prompt_record(record)
                    if not is_valid:
                        invalid_records.append(InvalidRecordInfo(
                            file="prompts.jsonl",
                            line_number=idx,
                            record_id=record.get("prompt_id") if isinstance(record, dict) else None,
                            reason=reason or "Validation failed"
                        ))
                    else:
                        valid_prompt_count += 1
                        valid_prompt_ids.add(record["prompt_id"])
                except Exception as e:
                    invalid_records.append(InvalidRecordInfo(
                        file="prompts.jsonl",
                        line_number=idx,
                        reason=f"Malformed JSON: {str(e)}"
                    ))

    # 2. Responses
    responses_path = os.path.join(source_directory, "responses.jsonl")
    valid_responses: List[Dict[str, Any]] = []

    if os.path.exists(responses_path):
        with open(responses_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    is_valid, reason = validate_response_record(record)
                    if not is_valid:
                        invalid_records.append(InvalidRecordInfo(
                            file="responses.jsonl",
                            line_number=idx,
                            record_id=record.get("response_id") if isinstance(record, dict) else None,
                            reason=reason or "Validation failed"
                        ))
                    else:
                        valid_responses.append(record)
                except Exception as e:
                    invalid_records.append(InvalidRecordInfo(
                        file="responses.jsonl",
                        line_number=idx,
                        reason=f"Malformed JSON: {str(e)}"
                    ))

    # Existing responses map to prevent duplicate entries
    existing_responses = {
        r.source_response_id: r
        for r in db.query(DBResponse).filter(DBResponse.dataset_id == dataset.id).all()
    }

    response_id_map: Dict[str, str] = {}  # source_response_id -> DB response.id

    for resp in valid_responses:
        s_id = resp["response_id"]
        if s_id in existing_responses:
            response_id_map[s_id] = existing_responses[s_id].id
        else:
            db_resp = DBResponse(
                dataset_id=dataset.id,
                source_response_id=s_id,
                prompt_id=resp["prompt_id"],
                engine=resp["engine"],
                raw_payload=json.dumps(resp),
            )
            db.add(db_resp)
            db.flush()
            existing_responses[s_id] = db_resp
            response_id_map[s_id] = db_resp.id

    # 3. Citations
    citations_path = os.path.join(source_directory, "citations.jsonl")
    valid_citation_count = 0

    # Existing citation source IDs to avoid duplicates
    existing_citations = {
        c.source_citation_id
        for c in db.query(DBCitation.source_citation_id)
        .join(DBResponse)
        .filter(DBResponse.dataset_id == dataset.id)
        .all()
    }

    if os.path.exists(citations_path):
        with open(citations_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    is_valid, reason = validate_citation_record(record)
                    if not is_valid:
                        invalid_records.append(InvalidRecordInfo(
                            file="citations.jsonl",
                            line_number=idx,
                            record_id=record.get("citation_id") if isinstance(record, dict) else None,
                            reason=reason or "Validation failed"
                        ))
                    else:
                        s_resp_id = record["response_id"]
                        if s_resp_id in response_id_map:
                            c_id = record["citation_id"]
                            if c_id not in existing_citations:
                                db_citation = DBCitation(
                                    response_id=response_id_map[s_resp_id],
                                    source_citation_id=c_id,
                                    prompt_id=record["prompt_id"],
                                    engine=record["engine"],
                                    order=record["order"],
                                    citation_type=record["citation_type"],
                                    url=record["url"],
                                    publication_date=record.get("publication_date")
                                )
                                db.add(db_citation)
                                existing_citations.add(c_id)
                            valid_citation_count += 1
                        else:
                            invalid_records.append(InvalidRecordInfo(
                                file="citations.jsonl",
                                line_number=idx,
                                record_id=record.get("citation_id"),
                                reason=f"Referenced response_id '{s_resp_id}' not found in valid responses"
                            ))
                except Exception as e:
                    invalid_records.append(InvalidRecordInfo(
                        file="citations.jsonl",
                        line_number=idx,
                        reason=f"Malformed JSON: {str(e)}"
                    ))

    db.commit()

    return DatasetImportResponse(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        imported_prompts=valid_prompt_count,
        imported_responses=len(existing_responses),
        imported_citations=valid_citation_count,
        invalid_records=invalid_records,
        validation_status="valid" if not invalid_records else "partial"
    )

