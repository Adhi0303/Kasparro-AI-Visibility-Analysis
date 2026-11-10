import os
import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Sequence
from sqlalchemy.orm import Session
from app.models import Dataset, Response as DBResponse, Citation as DBCitation
from app.schemas import DatasetImportResponse, InvalidRecordInfo


VALID_ENGINES = {"aimode", "chatgpt", "gemini"}
VALID_CITATION_TYPES = {"inline_hyperlink", "sources_panel"}
DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_RECORDS_PER_FILE = 10000


class PathSecurityError(ValueError):
    """Raised when an import directory fails path-boundary or symlink validation."""


class ImportLimitError(ValueError):
    """Raised when an import payload exceeds configured byte or record count limits."""


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


def validate_safe_source_directory(
    source_directory: str,
    allowed_roots: Optional[Sequence[Path]] = None,
) -> Path:
    """
    Validates source_directory against traversal, null bytes, non-directory targets,
    and (when supplied) permitted root directories using Path.is_relative_to().
    """
    if not source_directory or not source_directory.strip() or "\x00" in source_directory:
        raise PathSecurityError("Invalid dataset directory specification")

    raw_parts = source_directory.replace("\\", "/").split("/")
    if ".." in raw_parts:
        raise PathSecurityError("Path traversal segments are not permitted")

    candidate = Path(source_directory)
    if allowed_roots is not None:
        if candidate.is_absolute():
            raise PathSecurityError("Absolute paths are not permitted")
        resolved = (Path.cwd().resolve() / candidate).resolve()
        resolved_roots = [Path(r).resolve() for r in allowed_roots]
        if not any(resolved.is_relative_to(root) for root in resolved_roots):
            raise PathSecurityError("Directory lies outside authorized import roots")
    else:
        resolved = candidate.resolve()

    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError("Dataset source directory not found")

    # Verify individual .jsonl targets inside the directory do not escape via symlinks
    base_dir = resolved
    for fname in ("prompts.jsonl", "responses.jsonl", "citations.jsonl"):
        fpath = base_dir / fname
        if fpath.exists():
            real_fpath = fpath.resolve()
            if not real_fpath.is_relative_to(base_dir) or not real_fpath.is_file():
                raise PathSecurityError(f"Unsafe file target '{fname}' outside import directory")

    return resolved


def _valid_string(value: Any, *, max_length: int, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, str)
        and (allow_empty or bool(value.strip()))
        and len(value) <= max_length
        and "\\x00" not in value
    )


def validate_prompt_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(record, dict):
        return False, "Record is not a valid JSON object"
    for field in ("prompt_id", "run_id", "text"):
        if field not in record or record[field] is None:
            return False, f"Missing required prompt field: {field}"
    if not _valid_string(record["prompt_id"], max_length=128):
        return False, "prompt_id must be a non-empty string of at most 128 characters"
    if not _valid_string(record["run_id"], max_length=128):
        return False, "run_id must be a non-empty string of at most 128 characters"
    if not _valid_string(record["text"], max_length=50000):
        return False, "Prompt text must be a non-empty string of at most 50000 characters"
    return True, None


def validate_response_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(record, dict):
        return False, "Record is not a valid JSON object"
    for field in ("response_id", "run_id", "prompt_id", "engine", "answer_text", "capture_status"):
        if field not in record or record[field] is None:
            return False, f"Missing required response field: {field}"
    string_limits = {
        "response_id": 128,
        "run_id": 128,
        "prompt_id": 128,
        "engine": 32,
        "capture_status": 32,
        "answer_text": 200000,
    }
    for field, max_length in string_limits.items():
        if not _valid_string(record[field], max_length=max_length):
            return False, f"{field} must be a non-empty string of at most {max_length} characters"
    if record["engine"] not in VALID_ENGINES:
        return False, f"Invalid engine: {record['engine']}. Must be one of {VALID_ENGINES}"
    if record["capture_status"] != "captured":
        return False, f"Invalid capture_status: {record['capture_status']}. Must be 'captured'"
    return True, None


def validate_citation_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    if not isinstance(record, dict):
        return False, "Record is not a valid JSON object"
    required = ("citation_id", "response_id", "prompt_id", "engine", "order", "citation_type", "url")
    for field in required:
        if field not in record or record[field] is None:
            return False, f"Missing required citation field: {field}"
    limits = {
        "citation_id": 128,
        "response_id": 128,
        "prompt_id": 128,
        "engine": 32,
        "citation_type": 32,
        "url": 2048,
    }
    for field, max_length in limits.items():
        if not _valid_string(record[field], max_length=max_length):
            return False, f"{field} must be a non-empty string of at most {max_length} characters"
    if record["engine"] not in VALID_ENGINES:
        return False, f"Invalid engine: {record['engine']}"
    if record["citation_type"] not in VALID_CITATION_TYPES:
        return False, f"Invalid citation_type: {record['citation_type']}"
    if isinstance(record["order"], bool) or not isinstance(record["order"], int) or record["order"] < 1:
        return False, "Order must be an integer >= 1"
    if not record["url"].startswith(("https://", "http://")):
        return False, "Citation URL must use http or https"
    publication_date = record.get("publication_date")
    if publication_date is not None and not _valid_string(publication_date, max_length=64):
        return False, "publication_date must be a string of at most 64 characters"
    return True, None


def _check_file_limits(filepath: Path, max_file_bytes: int) -> None:
    if not filepath.exists():
        return
    size = filepath.stat().st_size
    if size > max_file_bytes:
        raise ImportLimitError(
            f"Import file '{filepath.name}' exceeds maximum permitted size ({max_file_bytes} bytes)"
        )


def import_dataset(
    db: Session,
    dataset_name: str,
    source_directory: str,
    owner_id: str = "analyst-1",
    allowed_roots: Optional[Sequence[Path]] = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_records_per_file: int = DEFAULT_MAX_RECORDS_PER_FILE,
) -> DatasetImportResponse:
    safe_dir = validate_safe_source_directory(source_directory, allowed_roots=allowed_roots)
    safe_dir_str = str(safe_dir)

    prompts_path = safe_dir / "prompts.jsonl"
    responses_path = safe_dir / "responses.jsonl"
    citations_path = safe_dir / "citations.jsonl"

    _check_file_limits(prompts_path, max_file_bytes)
    _check_file_limits(responses_path, max_file_bytes)
    _check_file_limits(citations_path, max_file_bytes)

    source_hash = compute_directory_hash(safe_dir_str)
    invalid_records: List[InvalidRecordInfo] = []

    try:
        # Scope dataset reuse strictly per (dataset_name, owner_id) for multi-tenant isolation
        dataset = (
            db.query(Dataset)
            .filter(Dataset.name == dataset_name, Dataset.owner_id == owner_id)
            .first()
        )
        if not dataset:
            dataset = Dataset(
                name=dataset_name,
                owner_id=owner_id,
                source_hash=source_hash,
                validation_status="valid",
            )
            db.add(dataset)
            db.flush()

        # 1. Prompts
        valid_prompt_count = 0
        valid_prompt_ids = set()
        prompt_texts_by_id: Dict[str, str] = {}
        prompts_file_exists = prompts_path.exists()

        if prompts_file_exists:
            with prompts_path.open("r", encoding="utf-8") as f:
                non_empty_lines = 0
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    non_empty_lines += 1
                    if non_empty_lines > max_records_per_file:
                        raise ImportLimitError(
                            f"prompts.jsonl exceeds maximum record limit ({max_records_per_file})"
                        )
                    try:
                        record = json.loads(line)
                        is_valid, reason = validate_prompt_record(record)
                        if not is_valid:
                            invalid_records.append(InvalidRecordInfo(
                                file="prompts.jsonl",
                                line_number=idx,
                                record_id=record.get("prompt_id") if isinstance(record, dict) else None,
                                reason=reason or "Validation failed",
                            ))
                        else:
                            pid = record["prompt_id"]
                            if pid in valid_prompt_ids:
                                invalid_records.append(InvalidRecordInfo(
                                    file="prompts.jsonl",
                                    line_number=idx,
                                    record_id=pid,
                                    reason=f"Duplicate prompt_id '{pid}' in prompts.jsonl",
                                ))
                            else:
                                valid_prompt_count += 1
                                valid_prompt_ids.add(pid)
                                prompt_texts_by_id[pid] = record.get("text", "")
                    except Exception:
                        invalid_records.append(InvalidRecordInfo(
                            file="prompts.jsonl",
                            line_number=idx,
                            reason="Malformed JSON object",
                        ))

        # 2. Responses
        valid_responses: List[Dict[str, Any]] = []
        seen_response_ids_in_file = set()

        if responses_path.exists():
            with responses_path.open("r", encoding="utf-8") as f:
                non_empty_lines = 0
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    non_empty_lines += 1
                    if non_empty_lines > max_records_per_file:
                        raise ImportLimitError(
                            f"responses.jsonl exceeds maximum record limit ({max_records_per_file})"
                        )
                    try:
                        record = json.loads(line)
                        is_valid, reason = validate_response_record(record)
                        if not is_valid:
                            invalid_records.append(InvalidRecordInfo(
                                file="responses.jsonl",
                                line_number=idx,
                                record_id=record.get("response_id") if isinstance(record, dict) else None,
                                reason=reason or "Validation failed",
                            ))
                            continue

                        s_id = record["response_id"]
                        if s_id in seen_response_ids_in_file:
                            invalid_records.append(InvalidRecordInfo(
                                file="responses.jsonl",
                                line_number=idx,
                                record_id=s_id,
                                reason=f"Duplicate response_id '{s_id}' in responses.jsonl",
                            ))
                            continue

                        if prompts_file_exists and record["prompt_id"] not in valid_prompt_ids:
                            invalid_records.append(InvalidRecordInfo(
                                file="responses.jsonl",
                                line_number=idx,
                                record_id=s_id,
                                reason=f"Referenced prompt_id '{record['prompt_id']}' not found in valid prompts",
                            ))
                            continue

                        seen_response_ids_in_file.add(s_id)
                        valid_responses.append(record)
                    except Exception:
                        invalid_records.append(InvalidRecordInfo(
                            file="responses.jsonl",
                            line_number=idx,
                            reason="Malformed JSON object",
                        ))

        # Existing responses map to guarantee idempotency across re-imports
        existing_responses = {
            r.source_response_id: r
            for r in db.query(DBResponse).filter(DBResponse.dataset_id == dataset.id).all()
        }

        response_id_map: Dict[str, str] = {}
        for r_sid, r_obj in existing_responses.items():
            response_id_map[r_sid] = r_obj.id

        for resp in valid_responses:
            s_id = resp["response_id"]
            if s_id in existing_responses:
                response_id_map[s_id] = existing_responses[s_id].id
            else:
                payload_to_store = dict(resp)
                if not payload_to_store.get("prompt_text") and resp["prompt_id"] in prompt_texts_by_id:
                    payload_to_store["prompt_text"] = prompt_texts_by_id[resp["prompt_id"]]
                db_resp = DBResponse(
                    dataset_id=dataset.id,
                    source_response_id=s_id,
                    prompt_id=resp["prompt_id"],
                    engine=resp["engine"],
                    raw_payload=json.dumps(payload_to_store),
                )
                db.add(db_resp)
                db.flush()
                existing_responses[s_id] = db_resp
                response_id_map[s_id] = db_resp.id

        # 3. Citations
        valid_citation_count = 0
        existing_citations = {
            c.source_citation_id
            for c in db.query(DBCitation.source_citation_id)
            .join(DBResponse)
            .filter(DBResponse.dataset_id == dataset.id)
            .all()
        }
        seen_citation_ids_in_file = set()

        if citations_path.exists():
            with citations_path.open("r", encoding="utf-8") as f:
                non_empty_lines = 0
                for idx, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    non_empty_lines += 1
                    if non_empty_lines > max_records_per_file:
                        raise ImportLimitError(
                            f"citations.jsonl exceeds maximum record limit ({max_records_per_file})"
                        )
                    try:
                        record = json.loads(line)
                        is_valid, reason = validate_citation_record(record)
                        if not is_valid:
                            invalid_records.append(InvalidRecordInfo(
                                file="citations.jsonl",
                                line_number=idx,
                                record_id=record.get("citation_id") if isinstance(record, dict) else None,
                                reason=reason or "Validation failed",
                            ))
                        else:
                            c_id = record["citation_id"]
                            if c_id in seen_citation_ids_in_file:
                                invalid_records.append(InvalidRecordInfo(
                                    file="citations.jsonl",
                                    line_number=idx,
                                    record_id=c_id,
                                    reason=f"Duplicate citation_id '{c_id}' in citations.jsonl",
                                ))
                                continue
                            seen_citation_ids_in_file.add(c_id)

                            s_resp_id = record["response_id"]
                            if s_resp_id in response_id_map:
                                if c_id not in existing_citations:
                                    db_citation = DBCitation(
                                        response_id=response_id_map[s_resp_id],
                                        source_citation_id=c_id,
                                        prompt_id=record["prompt_id"],
                                        engine=record["engine"],
                                        order=record["order"],
                                        citation_type=record["citation_type"],
                                        url=record["url"],
                                        publication_date=record.get("publication_date"),
                                    )
                                    db.add(db_citation)
                                    existing_citations.add(c_id)
                                valid_citation_count += 1
                            else:
                                invalid_records.append(InvalidRecordInfo(
                                    file="citations.jsonl",
                                    line_number=idx,
                                    record_id=c_id,
                                    reason=f"Referenced response_id '{s_resp_id}' not found in valid responses",
                                ))
                    except Exception:
                        invalid_records.append(InvalidRecordInfo(
                            file="citations.jsonl",
                            line_number=idx,
                            reason="Malformed JSON object",
                        ))

        if invalid_records:
            dataset.validation_status = "partial"
        db.commit()
    except Exception:
        db.rollback()
        raise

    return DatasetImportResponse(
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        imported_prompts=valid_prompt_count,
        imported_responses=len(existing_responses),
        imported_citations=valid_citation_count,
        invalid_records=invalid_records,
        validation_status="valid" if not invalid_records else "partial",
    )
