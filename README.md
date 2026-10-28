# Kasparro AI Visibility Analysis & Human Review Backend

**Pack Version:** 1.0.0  
**Creator:** ADARSH S  
**Role:** AI Software Engineer I (Assignment)  
**Execution Modes:** Keyless Replay (Default) & Real-Model Adapter  
**Persistence:** SQLite (`kasparro.db`)  
**API Framework:** FastAPI + Uvicorn  

---

## 1. Executive Summary

This service is a reproducible backend analytics platform that measures how **Kasparro** is represented across three leading generative AI answer engines: **Google AI Mode**, **ChatGPT**, and **Gemini**.

The system ingests a historical snapshot of **50 prompts**, **150 archived responses**, and **2,439 returned citations** (captured 31 July 2026), extracts structured brand visibility observations, computes a deterministic visibility score (0–100), surfaces evidence-backed diagnostics, and enforces human review before export.

---

## 2. Architecture & Design Principles

```mermaid
flowchart TD
    subgraph INGEST ["1. Data Ingestion & Provenance"]
        D1["50 Prompts"] & D2["150 Responses"] & D3["2,439 Citations"] --> HASH["SHA-256 Checksum & Schema Validation"]
        HASH --> DB[("SQLite Storage (kasparro.db)\n8 Relational Tables & Foreign Keys")]
    end

    subgraph CLASSIFY ["2. Dual Classifier & Scoring Engine"]
        DB --> ROUTE{"Execution Mode"}
        ROUTE -->|"Keyless Replay (Default)"| REPLAY["Deterministic Replay Classifier\n(Fast, offline, zero API keys)"]
        ROUTE -->|"Real Model Adapter"| PROV["LLM Provider Adapter\n(OpenAI / Google API + Retries)"]
        REPLAY & PROV --> SCORE["Visibility Scoring Engine (Formula v1)\n30% Inclusion + 40% Recommendation\n+ 20% Prominence + 10% Non-Negative"]
    end

    subgraph GOVERN ["3. Governance & Human Review"]
        SCORE --> DRAFT["Version 1: DRAFT\nAnalyst creates & edits findings"]
        DRAFT --> SUBMIT["Version 1: SUBMITTED\nAnalyst freezes version for audit"]
        SUBMIT --> DECIDE{"Reviewer Role Gate"}
        DECIDE -->|"Approve"| APP["Version 1: APPROVED\nCryptographic SHA-256 Lock"]
        DECIDE -->|"Reject"| REJ["Version 1: REJECTED\nExport Blocked (HTTP 400)"]
    end

    subgraph DELIVER ["4. Delivery & Interactive Visuals"]
        APP --> EXP["Export Gate (HTTP 200)\nImmutable JSON (final_report.json)"]
        APP --> HTML["Interactive Executive Dashboard\n(evaluation/results/report.html)"]
    end
```

### Core Design Principles:
1. **Evidence Before Conclusions:** Every diagnostic and remedy references specific `response_id`s and verbatim source excerpts. Hallucinated or non-verbatim excerpts are automatically flagged and rejected.
2. **Deterministic Calculations:** Scoring formulas, component weights, and aggregations are strictly deterministic in application code.
3. **Visible Failures:** Provider timeouts and malformed responses are recorded as explicit failures with a `failure_reason`, rather than silently manufactured as zero-score records.
4. **Approval-Gated Publication:** Reports follow a strict `DRAFT → SUBMITTED → APPROVED/REJECTED` state machine. Only immutable, approved versions can be exported. Editing an approved report automatically spawns a new unapproved draft.

---

## 3. Quick-Start Guide

### ⚡ Option A: One-Click End-to-End Demo (< 1 second)
Run the entire workflow (pack validation → SQLite setup → ingestion → deterministic scoring → export gate enforcement) in a single command:
```powershell
python demo.py
```

---

### 🛠️ Option B: Manual Step-by-Step Setup

### Step 1: Environment Setup
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt

# Configure environment file
copy .env.example .env
```

### Step 2: Verify Pack Integrity
```powershell
python tools/check_pack.py
```

### Step 3: Initialize Database Schema
```powershell
python -m app.database
```
*Creates all 8 relational tables in `kasparro.db`.*

### Step 4: Launch the API Server
```powershell
uvicorn app.main:app --reload
```
*Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.*

---

## 4. Running Automated Tests

Run the comprehensive 21-test pytest suite:
```powershell
pytest -v
```

Tests cover:
- Bearer token authentication & role isolation (`test_permissions.py`)
- Ingestion data integrity, SHA-256 hash, and idempotency (`test_ingestion.py`)
- Replay classifier, timeouts, and provider errors (`test_analysis.py`)
- Scoring formula, prominence decay, and aggregates (`test_scoring.py`)
- Report versioning and draft immutability (`test_reports.py`)
- Export gate enforcement (`test_export.py`)
- End-to-end REST API workflows (`test_api_integration.py`)

---

## 5. Running Evaluation & Grader

Run the evaluation script comparing the proposed classifier against a rule-based baseline across gold-standard labeled cases:
```powershell
python -m evaluation.run_eval
```
*Outputs: `evaluation/results/eval_comparison_report.md` and `evaluation/results/eval_results.json`.*

---

## 6. Execution Modes (Replay vs. Real-Model)

The system supports two execution modes configured in `.env`:

### Replay Mode (Default — No API Key Required)
```dotenv
EXECUTION_MODE=replay
```
- Uses the keyless deterministic classifier (`app/llm/replay.py`).
- Accurately parses regex patterns, extracts verbatim substrings, and tests simulated provider outages.

### Real-Model Adapter Mode
```dotenv
EXECUTION_MODE=real_model
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your_api_key_here
LLM_TIMEOUT_SECONDS=20
LLM_MAX_RETRIES=2
```
- Invokes external OpenAI-compatible chat completion endpoints.
- Constrained system prompt returns strict JSON schema; enforces retry limits and validates evidence excerpts.

---

## 7. REST API Endpoints & Example Calls

Default development tokens configured in `.env`:
- **Analyst Token:** `dev-analyst-token-2026`
- **Reviewer Token:** `dev-reviewer-token-2026`

### 1. Health Check
```powershell
curl http://127.0.0.1:8000/health
```

### 2. Ingest Dataset
```powershell
curl -X POST http://127.0.0.1:8000/datasets `
  -H "Authorization: Bearer dev-analyst-token-2026" `
  -H "Content-Type: application/json" `
  -d '{"dataset_name": "kasparro-historical-snapshot", "source_directory": "data"}'
```

### 3. Run Visibility Analysis
```powershell
curl -X POST http://127.0.0.1:8000/analyses `
  -H "Authorization: Bearer dev-analyst-token-2026" `
  -H "Content-Type: application/json" `
  -d '{"dataset_id": "<DATASET_ID>", "execution_mode": "replay"}'
```

### 4. Create & Submit Report
```powershell
# Create initial draft
curl -X POST "http://127.0.0.1:8000/reports?dataset_id=<DATASET_ID>" `
  -H "Authorization: Bearer dev-analyst-token-2026"

# Submit draft for review
curl -X POST "http://127.0.0.1:8000/reports/<REPORT_ID>/submit" `
  -H "Authorization: Bearer dev-analyst-token-2026"
```

### 5. Review Decision (Reviewer Only)
```powershell
curl -X POST "http://127.0.0.1:8000/reports/<REPORT_ID>/decision" `
  -H "Authorization: Bearer dev-reviewer-token-2026" `
  -H "Content-Type: application/json" `
  -d '{"version_id": "<VERSION_ID>", "decision": "approve", "comment": "Verified against source excerpts."}'
```

### 6. Export Approved Report
```powershell
curl -X GET "http://127.0.0.1:8000/reports/<REPORT_ID>/export" `
  -H "Authorization: Bearer dev-analyst-token-2026"
```

---

## 8. Detailed Technical Documentation (`docs/`)

The repository includes a dedicated documentation suite in the [`docs/`](docs/README.md) directory, structured into focused, single-topic guides:

| File Path | Document Title | Description & Scope |
| :--- | :--- | :--- |
| [`docs/README.md`](docs/README.md) | **Documentation Index** | High-level index, table of contents, and quick navigation across all documentation guides. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **System Architecture & Design** | Detailed system flow, complete SQLite Entity-Relationship (ER) model across all 8 tables, directory responsibilities, and engineering trade-offs. |
| [`docs/SCORING_AND_METHODOLOGY.md`](docs/SCORING_AND_METHODOLOGY.md) | **Scoring Methodology & Formula v1** | Mathematical derivation of Visibility Formula v1, component weights (30/40/20/10), positional reciprocal decay ($1/\text{rank}$), `null` uncertainty normalization, and statistical denominator hygiene. |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | **REST API Reference & Integration** | Complete OpenAPI/FastAPI endpoint specifications (`/datasets`, `/analyses`, `/reports`, `/decision`, `/export`), Bearer token RBAC authentication, and end-to-end cURL workflows. |
| [`docs/HUMAN_REVIEW_LIFECYCLE.md`](docs/HUMAN_REVIEW_LIFECYCLE.md) | **Human Review & Governance** | Analyst vs Reviewer workflow, state machine transitions (`DRAFT → SUBMITTED → APPROVED/REJECTED`), cryptographic SHA-256 content hashing, version immutability, and export gate enforcement. |
| [`docs/EVALUATION_AND_BENCHMARKS.md`](docs/EVALUATION_AND_BENCHMARKS.md) | **Evaluation & Benchmark Insights** | Ground-truth benchmark across 10 gold cases, baseline regex comparison (+20% agreement improvement), 3 evidence-backed diagnostics with verbatim source excerpts, and the prioritized remedies roadmap. |



