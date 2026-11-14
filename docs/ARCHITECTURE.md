# System Architecture & Technical Design

## 1. High-Level Architecture Overview

The Kasparro AI Visibility Analysis & Human Review service is an assignment-scale FastAPI backend designed for reproducible, evidence-backed evaluation of brand visibility across Generative AI answer engines (OpenAI ChatGPT, Google Gemini, and Google AI Mode).

```mermaid
flowchart TD
    subgraph Ingestion ["1. Ingestion Layer"]
        RAW["Raw Data Files\n(prompts, responses, citations)"] --> HASH["SHA-256 Provenance\n& Schema Validation"]
        HASH --> DB_INGEST[("SQLite Storage\nDatasets, Responses, Citations")]
    end

    subgraph Processing ["2. Analysis & Classification"]
        DB_INGEST --> ROUTER{"Execution Mode"}
        ROUTER -->|"Replay"| REPLAY["Deterministic Replay Classifier\n(Keyless Heuristics & Failure Stubs)"]
        ROUTER -->|"Provider"| ADAPTER["Real-Model Adapter\n(OpenAI-compatible Chat Completions)"]
        REPLAY --> RESULTS["Response Results\n(Mention, Rec, Neg, Position, Citations)"]
        ADAPTER --> RESULTS
        RESULTS --> SCORER["Deterministic Scoring Engine\n(Formula v1 + Aggregate Rollups)"]
    end

    subgraph Governance ["3. Human Review & Immutability"]
        SCORER --> DRAFT["Report Version (DRAFT)\nCreated by Analyst"]
        DRAFT --> SUBMIT["Report Version (SUBMITTED)\nLocked by Analyst"]
        SUBMIT --> DECISION{"Reviewer Gate"}
        DECISION -->|"Approve"| APPROVED["Report Version (APPROVED)\nContent Hash Locked"]
        DECISION -->|"Reject"| REJECTED["Report Version (REJECTED)\nExport Forbidden"]
        APPROVED --> EXPORT["Export Gate (HTTP 200)\nImmutable JSON / HTML"]
    end
```

---

## 2. Relational Database Schema (SQLite)

The persistence layer uses SQLite managed via SQLAlchemy ORM. The relational model enforces strict referential integrity, foreign key constraints, and audit trails across 8 tables:

```mermaid
erDiagram
    DATASETS ||--o{ RESPONSES : contains
    RESPONSES ||--o{ CITATIONS : cites
    DATASETS ||--o{ ANALYSIS_RUNS : evaluates
    ANALYSIS_RUNS ||--o{ RESPONSE_RESULTS : produces
    RESPONSES ||--o{ RESPONSE_RESULTS : evaluated_by
    DATASETS ||--o{ REPORTS : summarizes
    REPORTS ||--o{ REPORT_VERSIONS : revisions
    REPORT_VERSIONS ||--o{ REVIEW_DECISIONS : reviewed_in

    DATASETS {
        string id PK
        string name
        string source_hash
        string validation_status
        datetime created_at
    }
    RESPONSES {
        string id PK
        string dataset_id FK
        string source_response_id
        string prompt_id
        string engine
        string answer_text
        string answer_markdown
        string capture_status
    }
    CITATIONS {
        string id PK
        string response_id FK
        string citation_id
        string url
        string domain
        string snippet
    }
    ANALYSIS_RUNS {
        string id PK
        string dataset_id FK
        string execution_mode
        string classifier_version
        string scoring_version
        string status
        datetime started_at
        datetime completed_at
    }
    RESPONSE_RESULTS {
        string id PK
        string analysis_id FK
        string response_id FK
        string status
        float score
        json labels_json
        json components_json
        json evidence_json
        string failure_reason
    }
    REPORTS {
        string id PK
        string dataset_id FK
        string current_draft_version_id
        datetime created_at
    }
    REPORT_VERSIONS {
        string id PK
        string report_id FK
        int version_number
        string status
        string content_hash
        json content_json
        string created_by
        datetime created_at
        datetime submitted_at
    }
    REVIEW_DECISIONS {
        string id PK
        string report_version_id FK
        string reviewer_id
        string decision
        string comment
        datetime created_at
    }
```

---

## 3. Directory Layout & Module Responsibilities

The codebase follows a modular single-responsibility structure:

```
Kasparro_AI_Engineer_Fresher/
├── app/
│   ├── main.py             # FastAPI application router, lifespan, and health endpoints
│   ├── config.py           # Pydantic Settings reading .env (tokens, db url, timeouts)
│   ├── auth.py             # RBAC Bearer token dependency injection (Analyst vs Reviewer)
│   ├── database.py         # SQLAlchemy engine, session maker, init_db()
│   ├── models.py           # SQLAlchemy ORM class definitions
│   ├── schemas.py          # Pydantic v2 validation contracts for requests & responses
│   ├── ingestion.py        # Stream-based parsing, SHA-256 hashing, and idempotent insertion
│   ├── classification.py   # Analysis execution coordinator and status polling
│   ├── scoring.py          # Deterministic visibility score calculation & aggregate rollups
│   ├── evidence.py         # Verbatim substring verification & URL normalization
│   ├── diagnostics.py      # Evidence-backed findings with real response IDs & excerpts
│   ├── remedies.py         # Prioritized action items with baselines and evaluation criteria
│   ├── reports.py          # Draft creation, editing, and freeze-to-submit logic
│   ├── review.py           # Reviewer approval/rejection decision recording
│   ├── export.py           # Cryptographic approval gate enforcing immutable export
│   └── llm/
│       ├── base.py         # Abstract Base Class defining classifier interface
│       ├── replay.py       # Deterministic keyless replay classifier with failure simulation
│       └── provider.py     # Live API client with exponential backoff and schema validation
├── data/                   # AUTHORITATIVE HISTORICAL INPUT DATA (read-only)
│   ├── prompts.jsonl       # 50 exact queries (25 branded, 25 unbranded category)
│   ├── responses.jsonl     # 150 captured AI answers (50 ChatGPT, 50 Gemini, 50 AI Mode)
│   ├── citations.jsonl     # 2,439 source citations returned across responses
│   ├── run.json            # Capture metadata (July 31, 2026, DataForSEO, India, English)
│   └── READ_ME.txt         # Dataset documentation
├── evaluation/             # Independent evaluation suite
│   ├── cases.jsonl         # 20 supplied/synthetic regression cases\n│   ├── held_out_cases.jsonl # 30 provisional synthetic held-out scenarios\n│   ├── split_manifest.json # Split definitions and annotation limitations
│   ├── grader.py           # Multi-label confusion counts, per-label metrics, and agreement calculator
│   ├── run_eval.py         # Separate regression and held-out benchmark runs
│   └── results/            # Benchmark outputs, final_report.json, and report.html
├── fixtures/               # Test fixtures and simulated failure conditions
├── tests/                  # Unit, integration, security, provider, and report regression tests
├── tools/                  # Pack checks, report regeneration, and artifact consistency validation
├── demo.py                 # One-click end-to-end demonstration script
├── README.md               # Quick-start manual and API usage guide
└── DECISION_NOTE.md        # Architectural decisions, trade-offs, and disclosures
```

---

## 4. Key Design Decisions

1. **Deterministic Application Layer**:
   Calculations, aggregations, and governance rules are hardcoded in application logic—never outsourced to LLM prompting. This guarantees 100% reproducibility across identical inputs.
2. **Keyless Replay by Default**:
   Evaluators can verify the entire pipeline without registering for third-party API accounts or supplying billing information.
3. **Failures as First-Class Citizens**:
   A failed API call or malformed response is never treated as a 0% visibility score or as an absent mention. It receives `status: failed`, records an explicit `failure_reason`, and is excluded from scoring denominators to avoid statistical distortion.


## 5. Generated Report Integrity

The interactive dashboard is a generated view of `evaluation/results/final_report.json`, the per-response `prompt_scores.json`, and the regression/held-out evaluation outputs. Run `python tools/regenerate_artifacts.py` after changing source data or analysis code, then run `python tools/validate_artifacts.py` to verify dashboard/JSON/Markdown consistency and source offsets for every displayed diagnostic excerpt. Dashboard metrics are not intended to be edited independently in HTML.
