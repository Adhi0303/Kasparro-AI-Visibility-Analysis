# Kasparro AI Visibility – Module Development Guide

> **Assignment:** AI Visibility Analysis and Human Review  
> **Role:** AI Software Engineer I (Fresher)  
> **Time Limit:** 6 active hours  
> **Stack:** Python 3.10+, FastAPI, SQLite, Pydantic, pytest  
> **Data:** 50 prompts · 150 responses · 2,439 citation occurrences (captured 31 Jul 2026)

---

## 🗺️ Project Overview

Kasparro is an AI-visibility analytics platform. **For this assignment, Kasparro itself is the brand being analysed** — we measure how it appears across ChatGPT (`chatgpt`), Gemini (`gemini`), and Google AI Mode (`aimode`).

The system ingests archived AI responses, classifies brand mentions, scores visibility, detects diagnostics, generates a structured report, and enforces an analyst → reviewer → export workflow.

---

## 📁 Repository Layout (Target)

```
kasparro-visibility/
├── app/
│   ├── main.py          ← FastAPI app entry point
│   ├── config.py        ← Environment / settings loader
│   ├── auth.py          ← Token-based role enforcement
│   ├── schemas.py       ← Pydantic request/response models
│   ├── database.py      ← SQLite init + SQLAlchemy session
│   ├── models.py        ← ORM table definitions
│   ├── ingestion.py     ← Import + validate data files
│   ├── classification.py← LLM / rule classifier
│   ├── scoring.py       ← Deterministic visibility score
│   ├── evidence.py      ← Excerpt extraction & validation
│   ├── diagnostics.py   ← 3 evidence-backed findings
│   ├── remedies.py      ← 3 prioritized remedies
│   ├── reports.py       ← Draft lifecycle management
│   ├── review.py        ← Approve / reject workflow
│   ├── export.py        ← Immutable-version export gate
│   └── llm/
│       ├── base.py      ← Abstract LLM interface
│       ├── replay.py    ← Deterministic stub (no API key)
│       └── provider.py  ← Real-model adapter (OpenAI etc.)
├── data/                ← ORIGINAL DATA — never modify
│   ├── prompts.jsonl
│   ├── responses.jsonl
│   ├── citations.jsonl
│   ├── run.json
│   └── READ_ME.txt
├── evaluation/
│   ├── cases.jsonl      ← Manual + synthetic eval labels
│   ├── grader.py        ← Precision / recall calculator
│   ├── run_eval.py      ← Eval entry point
│   └── results/         ← Written comparison reports
├── tests/
│   ├── test_ingestion.py
│   ├── test_analysis.py
│   ├── test_scoring.py
│   ├── test_permissions.py
│   ├── test_reports.py
│   └── test_export.py
├── tools/
│   └── check_pack.py    ← Pack integrity checker (provided)
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── DECISION_NOTE.md
```

---

## 🔑 Key Data Facts

| Item | Value |
|------|-------|
| Run ID | `4a4b71d9-9b0d-4497-85f1-7db5c4e21472` |
| Capture date | 31 July 2026 |
| Engines | `aimode`, `chatgpt`, `gemini` |
| Prompts | 50 |
| Responses | 150 (50 per engine) |
| Citation occurrences | 2,439 |
| Location / language | India / English |

Prompt IDs follow the pattern `kasparro:ai_shortlisting:001` … Responses carry full `answer_text` plus an optional `answer_markdown` (two views, one response — not two independent observations).

---

## 📐 Visibility Score Formula (v1)

$$\text{score} = 100 \times (0.30 \times \text{inclusion} + 0.40 \times \text{recommendation} + 0.20 \times \text{prominence} + 0.10 \times \text{non\_negative})$$

| Component | Weight | Rule |
|-----------|--------|------|
| Inclusion | 30% | 1.0 if Kasparro mentioned; 0.0 if absent |
| Recommendation | 40% | 1.0 if explicitly recommended |
| Prominence | 20% | position-decay (1/rank); `null` if unobservable |
| Non-negative | 10% | 1.0 if no negative characterization |

> [!IMPORTANT]
> A **failed** classification does not receive score 0. Mark it `status=failed` and exclude from score denominator. Unknown prominence stays `null`; do not fill with 0.

---

## 🏗️ Module Development Steps

Work through each module in order. Each section shows: **goal → files to create → acceptance criteria → status checkbox**.

---

### Module 0 — Environment & Pack Verification
**Goal:** Confirm data integrity, set up Python env, lay out folder skeleton.

**Steps:**
1. Verify pack integrity:
   ```powershell
   py -3 tools/check_pack.py
   ```
2. Create virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Create `requirements.txt`:
   ```
   fastapi>=0.111
   uvicorn[standard]>=0.29
   pydantic>=2.7
   pydantic-settings>=2.2
   sqlalchemy>=2.0
   aiosqlite
   python-dotenv
   httpx
   pytest
   pytest-asyncio
   ```
4. Install:
   ```powershell
   pip install -r requirements.txt
   ```
5. Copy `.env.example` → `.env` and fill tokens:
   ```dotenv
   APP_ENV=development
   DATABASE_URL=sqlite:///./kasparro.db
   EXECUTION_MODE=replay
   ANALYST_TOKEN=dev-analyst-token
   REVIEWER_TOKEN=dev-reviewer-token
   LLM_PROVIDER=
   LLM_MODEL=
   LLM_API_KEY=
   LLM_TIMEOUT_SECONDS=20
   LLM_MAX_RETRIES=2
   ```

**Acceptance:** `check_pack.py` exits 0; `pip install` succeeds; `.env` in place.

- [x] ✅ Done

---

### Module 1 — Configuration & Database (`config.py`, `database.py`, `models.py`)
**Goal:** Persist all data in SQLite with proper schema.

**Files to create:**

#### `app/config.py`
Load settings from `.env` using `pydantic-settings`:
- `DATABASE_URL`, `EXECUTION_MODE`, `ANALYST_TOKEN`, `REVIEWER_TOKEN`, `LLM_*` fields.

#### `app/models.py`
SQLAlchemy ORM classes — **6 tables:**

| Table | Key columns |
|-------|-------------|
| `Dataset` | id, name, source_hash, created_at, validation_status |
| `Response` | id, dataset_id, source_response_id, prompt_id, engine, raw_payload, imported_at |
| `AnalysisRun` | id, dataset_id, execution_mode, classifier_version, scoring_version, status, started_at, completed_at |
| `ResponseResult` | id, analysis_id, response_id, status, labels_json, components_json, score, evidence_json, failure_reason |
| `Report` | id, dataset_id, current_draft_version_id, created_at |
| `ReportVersion` | id, report_id, version_number, status (DRAFT/SUBMITTED/APPROVED/REJECTED), content_json, content_hash, created_by, created_at, submitted_at |
| `ReviewDecision` | id, report_version_id, reviewer_id, decision, comment, created_at |

#### `app/database.py`
- Create engine, `SessionLocal`, `Base`.
- `init_db()` function that calls `Base.metadata.create_all()`.
- `get_db()` FastAPI dependency.

**Init command:**
```powershell
python -m app.database
```

**Acceptance:** `kasparro.db` created with all 7 tables visible via `.tables`.

- [x] ✅ Done

---

### Module 2 — Authentication & Authorization (`auth.py`)
**Goal:** Enforce analyst vs reviewer roles via static tokens from env.

**Rules:**
- Token is passed in `Authorization: Bearer <token>` header.
- `ANALYST_TOKEN` → role `analyst`
- `REVIEWER_TOKEN` → role `reviewer`
- Any other value → HTTP 401
- Role is derived from config — **never** from a request body field.

**FastAPI dependencies:**
```python
def require_analyst(token: str = Depends(oauth2_scheme)) -> str: ...
def require_reviewer(token: str = Depends(oauth2_scheme)) -> str: ...
```

**Acceptance:** Unit test confirms analyst token gets role `analyst`; reviewer token gets role `reviewer`; bad token returns 401.

- [x] ✅ Done

---

### Module 3 — Data Ingestion & Validation (`ingestion.py`)
**Goal:** Import `prompts.jsonl`, `responses.jsonl`, `citations.jsonl` from `data/` into SQLite.

**REST endpoint:** `POST /datasets`
```json
{ "dataset_name": "kasparro-historical-snapshot", "source_directory": "data" }
```

**Validation rules (per `schemas/input_contract.json`):**
- Required fields: `prompt_id`, `run_id`, `text` (prompts); `response_id`, `prompt_id`, `engine`, `answer_text`, `capture_status` (responses); `citation_id`, `response_id`, `url` (citations).
- Engine must be one of `aimode`, `chatgpt`, `gemini`.
- `capture_status` must be `"captured"`.
- Null fields → store as `null`, never treat as zero.
- Duplicate `source_response_id` within same dataset → skip (idempotent), do not duplicate.
- One bad record must not reject other valid records.
- Compute `source_hash` (SHA-256) of the data directory for provenance.

**Response shape:**
```json
{
  "dataset_id": "...",
  "imported_prompts": 50,
  "imported_responses": 150,
  "imported_citations": 2439,
  "invalid_records": [],
  "validation_status": "valid"
}
```

**Acceptance:**
- `imported_responses == 150`, `imported_citations == 2439`.
- Re-running the same import returns identical counts without duplicating rows.
- A deliberately malformed record is logged in `invalid_records` but does not block the rest.

- [x] ✅ Done

---

### Module 4 — LLM Adapter (`llm/base.py`, `llm/replay.py`, `llm/provider.py`)
**Goal:** Abstract classifier interface with a keyless replay mode and a real-model adapter.

#### `llm/base.py`
```python
class LLMBase(ABC):
    @abstractmethod
    def classify(self, response_text: str, response_id: str) -> ClassificationResult: ...
```

#### `llm/replay.py`
Deterministic stub — no API key required. Uses `fixtures/failure_scenarios.json` to simulate failures for specific response IDs. For all others, returns a fixed label set based on keyword heuristics (case-insensitive substring match for "kasparro").

Rules:
- Always sets `execution_mode = "replay"`.
- Never marks replay as live-model output.
- Simulates timeout/malformed for IDs listed in `fixtures/failure_scenarios.json`.

#### `llm/provider.py`
Real-model adapter (e.g., OpenAI / Google). Reads `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` from config.

Flow:
1. Build a constrained prompt with the classification JSON schema.
2. Send `answer_text` as **untrusted data** (do not let it override system instructions).
3. Parse JSON response.
4. Validate against schema.
5. Retry up to `LLM_MAX_RETRIES` on parse failure.
6. On provider error / timeout → return `status=failed`, do not manufacture a label.

**Acceptance:** Replay runs with no API key; provider adapter is importable and documented even if credentials absent.

- [x] ✅ Done

---

### Module 5 — Classification (`classification.py`)
**Goal:** Classify every response and persist `ResponseResult`.

**Classification schema per response:**
```json
{
  "response_id": "...",
  "engine": "chatgpt",
  "status": "success|failed|skipped",
  "kasparro_absent": false,
  "kasparro_mentioned": true,
  "kasparro_recommended": false,
  "kasparro_negative": false,
  "competitors": ["profound", "..."],
  "recommendation_position": null,
  "citation_ids": [],
  "evidence": [{"excerpt": "...", "location": "answer_text"}],
  "confidence": null,
  "failure_reason": null,
  "execution_mode": "replay",
  "classifier_version": "v1"
}
```

**Label definitions:**
- **Absent**: No identifiable mention of Kasparro.
- **Mentioned**: Kasparro explicitly referenced.
- **Recommended**: Presented as a suitable option/provider.
- **Negative**: Characterised unfavourably.
- Labels may overlap (e.g., mentioned + negative).
- `failed ≠ absent`.

**REST endpoint:** `POST /analyses`
```json
{ "dataset_id": "...", "execution_mode": "replay", "classifier_version": "v1", "scoring_version": "v1" }
```
Returns `{ "analysis_id": "...", "status": "running" }`.

`GET /analyses/{id}` — poll status + results.

**Acceptance:**
- All 150 responses produce one of: `success`, `failed`, `skipped`.
- Failed results have a `failure_reason`.
- Evidence excerpts exist verbatim in `answer_text`.

- [x] ✅ Done

---

### Module 6 — Evidence Extraction & Validation (`evidence.py`)
**Goal:** Ensure every evidence excerpt actually exists in the source response.

**Rules:**
- Extract exact substring matches from `answer_text`.
- Reject any evidence where the excerpt cannot be located in the source text.
- Link evidence to `citation_ids` when a cited URL is within the excerpt context.
- Mark citation as `unverified` (we cannot inspect the external page).
- URL normalization: strip tracking params (`utm_*`), lowercase scheme+host, strip trailing slash — count unique normalized URLs separately from occurrences.

**Acceptance:** A test fixture with a fabricated excerpt is rejected/flagged by `validate_evidence()`.

- [x] ✅ Done

---

### Module 7 — Visibility Scoring (`scoring.py`)
**Goal:** Deterministic score computation with clear uncertainty handling.

**Formula (v1):** See section above.

**Prominence decay:**
```python
prominence = 1 / recommendation_position  # if position is known
# None if position unobservable
```

**Aggregation per engine / per category:**
- Use only `status=success` responses.
- Report separately: eligible, success, failed, skipped counts.
- Mean score over successfully scored responses.
- Distribution: % inclusion, % recommended, % negative.

**Acceptance:** Unit test with known component values matches expected score to 2 decimal places.

- [x] ✅ Done

---

### Module 8 — Prompt Categorization (inside `classification.py` or separate `categories.py`)
**Goal:** Assign each prompt to a category inferred from actual questions.

**Candidate categories** (derive from real prompts in `data/prompts.jsonl`):
- `brand_discovery` — "does kasparro…", "what is kasparro…"
- `vendor_comparison` — "is kasparro better than…", "kasparro vs…"
- `capability_evaluation` — "can kasparro help…", "does kasparro support…"
- `implementation` — "how does kasparro…", "how to use kasparro…"
- `purchase_intent` — "should I buy…", "is kasparro worth…"

Document the final taxonomy with a `category_version` string. Report category-level scores with denominators.

**Acceptance:** All 50 prompts assigned a category; taxonomy documented.

- [x] ✅ Done

---

### Module 9 — Diagnostics & Remedies (`diagnostics.py`, `remedies.py`)
**Goal:** Generate 3 evidence-backed diagnostics and 3 prioritized remedies from actual results.

> [!NOTE]
> Do not write diagnostics until actual dataset results are available. Placeholders must be replaced with real response IDs and excerpts.

**Each diagnostic must state:**
1. Observed pattern (with counts and denominators)
2. Comparison across engines or categories
3. Evidence: `response_id`, engine, prompt, exact excerpt
4. Possible explanation (hypothesis — not established cause)
5. Validation needed
6. Confidence and limitations (sample size, failures, ambiguity)

**Each remedy must state:**
- Problem (from diagnostic)
- Supporting evidence (response IDs)
- Action or investigation
- Expected benefit (no guarantee of ranking improvement)
- Effort: Low / Medium / High
- Uncertainty
- Validation: measurable criterion + baseline + evaluation period

**Acceptance:** Every diagnostic references ≥1 real response ID; excerpts verified in source.

- [x] ✅ Done

---

### Module 10 — Report Lifecycle (`reports.py`, `review.py`, `export.py`)
**Goal:** Full analyst → reviewer → export workflow with immutability.

#### Report State Machine

```
DRAFT ──► SUBMITTED ──► APPROVED ──► (export permitted)
                    └──► REJECTED ──► (export blocked)
```

After approving or submitting, editing creates a **new DRAFT version** — the old version is immutable.

#### `reports.py` — Draft management
- `PATCH /reports/{id}` — edit draft (analyst role); validates fields, persists, updates `content_hash`.
- `POST /reports/{id}/submit` — freeze to SUBMITTED; sets `submitted_at`; future edits create a new draft.

#### `review.py` — Review decisions
- `POST /reports/{id}/decision` — reviewer role only.
  ```json
  { "version_id": "...", "decision": "approve", "comment": "..." }
  ```
  - Reviewer identity derived from token — **not from request body**.
  - Persist decision in `ReviewDecision` (history preserved, not overwritten).

#### `export.py` — Export gate
- `GET /reports/{id}/export` — requires analyst or reviewer with export permission.
- **Blocks if:** status is `DRAFT`, `REJECTED`, or if report has been edited since approval (staleness check via `content_hash`).
- **Permits only** the exact approved immutable version.
- Returns full content: findings, evidence, remedies, review decision, provenance.

**Required demonstrations (write a test or curl sequence for each):**
1. Analyst attempting reviewer decision → 403
2. Rejected report export → 403
3. Approved report export → 200
4. Edit approved report → new DRAFT created, old version unchanged
5. New draft export blocked until reviewed
6. Old approved version remains identifiable and immutable

**Acceptance:** All 6 demonstrations pass.

- [x] ✅ Done

---

### Module 11 — Evaluation (`evaluation/`)
**Goal:** Separate from engineering tests — compares classifier quality against human labels.

#### Step 1: Manual labeling (`evaluation/cases.jsonl`)
Manually label **≥8 supplied responses** covering:
- All 3 engines
- Multiple prompt categories
- Present and absent mentions
- Recommendation cases
- Negative characterization cases
- Citation cases

Plus **2 synthetic edge cases** (marked `"source_type": "synthetic"`):
- e.g., response that mentions "Kasparro" only in a question recap (not a mention by the AI)
- e.g., response with ambiguous sentiment

Each case:
```json
{
  "case_id": "eval-001",
  "source_type": "supplied",
  "response_id": "ACTUAL_RESPONSE_ID",
  "expected": {
    "kasparro_mentioned": true,
    "kasparro_recommended": false,
    "kasparro_negative": true
  },
  "expected_evidence": ["exact excerpt from response"],
  "notes": "Negative characterization without recommendation."
}
```

#### Step 2: Rule-based baseline (`grader.py`)
Simple keyword matcher (no LLM) as baseline comparator.

#### Step 3: Metrics (`grader.py`)
For each label:
```
precision = TP / (TP + FP)   # undefined if denominator = 0
recall    = TP / (TP + FN)   # undefined if denominator = 0
```
Report: per-label precision/recall, agreement, score-calculation correctness, success/failed/skipped counts, evidence-validation failures.

#### Step 4: Failure report (required)
Document **one actual failure** using:
- **Failure:** what was observed
- **Diagnosis:** cause (from logs/fixtures)
- **Change:** fix implemented
- **Regression case:** test that prevents recurrence
- **Verification:** exact command + output

**Run evaluation:**
```powershell
python -m evaluation.run_eval
```
Writes a readable report to `evaluation/results/`.

**Acceptance:** Report includes baseline vs proposed, all metrics, failure documentation.

- [x] ✅ Done

---

### Module 12 — Automated Tests (`tests/`)
**Goal:** pytest suite covering all required scenarios.

| Test | File | Covers |
|------|------|--------|
| Invalid input | `test_ingestion.py` | Malformed record logged; valid records unaffected |
| Duplicate response | `test_ingestion.py` | Safe reuse; no duplication |
| Model timeout | `test_analysis.py` | Failure recorded; no result manufactured |
| Malformed model output | `test_analysis.py` | Retry then explicit failure |
| Wrong reviewer role | `test_permissions.py` | 403 on decision endpoint |
| Rejected report export | `test_export.py` | 403 |
| Edit after approval | `test_reports.py` | New draft created |
| Approved report export | `test_export.py` | 200 with immutable content |
| Unsupported evidence | `test_analysis.py` | Excerpt flagged/rejected |
| Deterministic scoring | `test_scoring.py` | Known inputs → expected score |

Use deterministic model stubs in all engineering tests. Clearly label stub vs real-model results.

**Run:**
```powershell
pytest -q
```

**Acceptance:** All 10 required test scenarios have at least one passing test.

- [x] ✅ Done

---

### Module 13 — API Wiring & Health Check (`main.py`)
**Goal:** Assemble FastAPI app; wire all routers; add health endpoint.

**Endpoints:**

| Method | Path | Auth | Module |
|--------|------|------|--------|
| GET | `/health` | none | main.py |
| POST | `/datasets` | analyst | ingestion |
| POST | `/analyses` | analyst | classification |
| GET | `/analyses/{id}` | analyst | classification |
| PATCH | `/reports/{id}` | analyst | reports |
| POST | `/reports/{id}/submit` | analyst | reports |
| POST | `/reports/{id}/decision` | reviewer | review |
| GET | `/reports/{id}/export` | analyst or reviewer | export |

`/docs` (Swagger UI) available automatically via FastAPI.

**Start server:**
```powershell
uvicorn app.main:app --reload
```

**Acceptance:** `curl http://127.0.0.1:8000/health` returns `{"status": "ok"}`; `/docs` renders all endpoints.

- [x] ✅ Done

---

### Module 14 — Final Report & Documentation
**Goal:** Produce the final deliverable and all required documents.

#### `README.md`
- Setup commands
- How to switch between replay and real-model mode
- How to run tests
- How to run evaluation
- Example API calls (curl) for each endpoint
- Known limitations

#### `DECISION_NOTE.md`
- Scoring weights rationale (versioned)
- Backend design choices
- Alternatives considered
- Top remedy (from actual evidence)
- Largest risk
- Unfinished work / omissions
- AI assistance disclosure (which tool, which tasks, what was verified)

#### Final JSON output (`evaluation/results/final_report.json`)
Must contain:
- Dataset and run provenance
- Prompt + response coverage
- Engine-level scores
- Category-level scores
- Label distributions
- Eligible / successful / failed / skipped counts
- 3 diagnostics (with real response IDs and excerpts)
- 3 remedies
- Score version + classifier version
- Execution mode
- Evaluation results
- Limitations and uncertainty

**Active-time log** (fill as you go):

| Activity | Actual time | Status |
|----------|-------------|--------|
| Read assignment and inspect data | | |
| Implement ingestion and validation | | |
| Implement classification and scoring | | |
| Implement APIs and persistence | | |
| Implement review and export controls | | |
| Implement evaluation and tests | | |
| Write documentation and decision note | | |
| **Total active time** | **≤ 6 hours** | |

- [x] ✅ Done

---

## ✅ Submission Checklist

- [x] Source code in private repo/archive
- [x] `python -m app.database` initializes DB
- [x] `requirements.txt` with pinned versions
- [x] `.env.example` present, no real secrets committed
- [x] Supplied data NOT in public Git history
- [x] Input validation + duplicate handling tested
- [x] Replay mode works without model API key
- [x] Real-model adapter documented (even if key absent)
- [x] Every response has result / failure / skipped reason
- [x] Scoring formula and uncertainty documented
- [x] ≥8 supplied responses manually labeled
- [x] 2 synthetic edge cases clearly identified
- [x] Rule-based baseline compared with proposed approach
- [x] One failure documented: failure → diagnosis → fix → regression test
- [x] Wrong-role denial demonstrated
- [x] Rejected report export blocked
- [x] Edit-after-approval creates new draft
- [x] Only approved immutable version exportable
- [x] 3 evidence-backed diagnostics with real response IDs
- [x] 3 prioritized remedies
- [x] Active-time log + omissions disclosed
- [x] AI assistance disclosed
- [x] Setup / test / eval / API commands documented
- [x] Final output verified against actual dataset

---

## 🚀 Quick-Start Commands (In Order)

```powershell
# 1. Verify pack
py -3 tools/check_pack.py

# 2. Create & activate venv
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env template
copy .env.example .env

# 5. Initialize database
python -m app.database

# 6. Start server
uvicorn app.main:app --reload

# 7. Health check
curl http://127.0.0.1:8000/health

# 8. Run tests
pytest -q

# 9. Run evaluation
python -m evaluation.run_eval
```

---

## ⚠️ Key Constraints to Never Forget

> [!CAUTION]
> - **Never modify** files under `data/` — they are the original authoritative inputs.
> - **Never commit** real API keys, tokens, or credentials.
> - **Never represent** replay results as live-model output.
> - **Never silently** treat failed classifications as absent mentions.
> - **Never allow** caller-supplied role names to grant permissions.
> - **Stop at 6 active hours** and disclose unfinished work.

> [!WARNING]
> - A citation is **not** evidence you have inspected the page — mark uninspected citations as `unverified`.
> - An older approval covers only that exact immutable version — it never authorizes newer unreviewed content.
> - Do not contact customers, publish findings, or execute remedies against any real system.

