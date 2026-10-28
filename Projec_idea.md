# Kasparro AI Engineer Assignment
## AI Visibility Analysis and Human Review

**Role:** AI Software Engineer I  
**Assignment:** AI visibility analysis and human review  
**Pack version:** 1.0  
**Implementation language:** Python 3.10+  
**Database:** SQLite  
**Execution modes:** Replay/stub and real-model adapter  
**Status:** Implementation and evaluation report — complete actual dataset results before submission

---

## 1. Executive Summary

This project implements a backend service that analyzes archived AI-generated answers to understand how Kasparro is represented across ChatGPT, Gemini, and Google AI Mode.

The system processes 50 prompts and 150 archived responses, extracts structured brand-visibility observations, calculates transparent scores, identifies evidence-backed diagnostics, and proposes prioritized remedies.

The system also supports human review. Analysts can import data, run analyses, and edit draft reports. Reviewers can approve or reject submitted report versions. Only an approved, non-stale, immutable report version can be exported.

The design follows four principles:

1. **Evidence before conclusions:** Every important finding must reference source response IDs and supporting excerpts.
2. **Deterministic calculations:** Counts, validation, score aggregation, versioning, and permissions are enforced by application code.
3. **Visible failures:** Failed or skipped analyses are recorded explicitly rather than silently treated as zero-score observations.
4. **Human-controlled publication:** A report cannot be exported merely because an analysis has completed.

The project is intended to produce a reproducible historical snapshot analysis, not a claim about current AI search rankings.

## 2. Problem Statement

Kasparro helps brands understand how they are represented in AI-generated answers.

The service must answer three questions:

- Where does Kasparro appear to be winning or losing in the supplied snapshot?
- What evidence supports each finding?
- What should be investigated or changed next?

The supplied data represents a historical run captured on 31 July 2026 in India and English through DataForSEO.

The dataset contains:

- 50 exact prompts.
- 150 archived responses, with one response per prompt from each of the three AI experiences.
- 2,439 returned citation occurrences.
- Original provider payloads and supporting reference files.

These records describe the supplied historical snapshot. They do not establish current rankings, current model behavior, or the accuracy of every cited source.

## 3. Scope and Constraints

### Included

- Input validation and dataset import.
- Structured response classification.
- Explicit visibility-score calculation.
- Evidence extraction and traceability.
- Comparison across engines and prompt categories.
- Three evidence-backed diagnostics.
- Three prioritized remedies.
- SQLite persistence.
- REST API endpoints.
- Analyst and reviewer permissions.
- Immutable report versions.
- Approval-controlled export.
- Replay mode and a real-model adapter.
- Evaluation cases, automated tests, and a reproducible comparison report.

### Excluded unless time permits

- A graphical dashboard.
- Docker deployment.
- Public hosting.
- Live crawling of AI search experiences.
- Paid external services without approved access.
- Multiple cooperating agents.
- Full OAuth authentication.
- Distributed job processing.

The assignment has a six-active-hour limit. Work must stop when that limit is reached, with actual time spent, omissions, and unfinished work disclosed.

## 4. Proposed Architecture

The backend is organized into separate modules.

```text
kasparro-visibility/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── auth.py
│   ├── schemas.py
│   ├── database.py
│   ├── models.py
│   ├── ingestion.py
│   ├── classification.py
│   ├── scoring.py
│   ├── evidence.py
│   ├── diagnostics.py
│   ├── remedies.py
│   ├── reports.py
│   ├── review.py
│   ├── export.py
│   └── llm/
│       ├── base.py
│       ├── replay.py
│       └── provider.py
├── data/
│   ├── prompts.jsonl
│   ├── responses.jsonl
│   ├── citations.jsonl
│   ├── run.json
│   └── READ_ME.txt
├── evaluation/
│   ├── cases.jsonl
│   ├── grader.py
│   ├── run_eval.py
│   └── results/
├── tests/
│   ├── test_ingestion.py
│   ├── test_analysis.py
│   ├── test_scoring.py
│   ├── test_permissions.py
│   ├── test_reports.py
│   └── test_export.py
├── tools/
│   └── check_pack.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── DECISION_NOTE.md
```

This is the proposed repository layout. Files should be created and tested as part of implementation; the layout alone does not establish that the application is runnable.

### Processing flow

```text
Input files
    |
    v
Validation and deduplication
    |
    v
Response classification
    |
    v
Evidence extraction and validation
    |
    v
Deterministic scoring
    |
    v
Engine and category aggregation
    |
    v
Diagnostics and remedies
    |
    v
Draft report
    |
    v
Analyst editing
    |
    v
Immutable submitted version
    |
    v
Reviewer approval or rejection
    |
    v
Approved-version-only export
```

## 5. Technology Choices

| Component | Proposed choice | Reason |
|---|---|---|
| Language | Python 3.10+ | Straightforward data processing and model integration |
| API framework | FastAPI | Request validation and generated API documentation |
| Persistence | SQLite | Sufficient for a small local assignment |
| Validation | Pydantic | Structured request and response validation |
| Model integration | Provider adapter | Keeps model-specific logic separate |
| Replay mode | Deterministic fixtures | Allows offline execution and failure testing |
| Testing | pytest | Repeatable automated checks |
| Evaluation | Python grader | Deterministic comparison against expected labels |

The actual model provider, model name, configuration, calls, and cost must be recorded when a real-model adapter is used. Replay results must never be represented as live-model results.

## 6. Input Validation and Data Integrity

The application preserves the supplied source files and original record identifiers.

### Validation requirements

- Validate required fields and data types.
- Preserve original prompt and response IDs.
- Preserve engine and model metadata as supplied.
- Represent unknown model versions and citation publication dates as unknown.
- Link citations to their original response IDs.
- Validate records independently so one malformed record does not erase valid records.
- Record invalid records with a reason and processing status.
- Reject or safely reuse repeated imports of the same identified response.
- Never silently duplicate an existing response.
- Keep source content separate from application instructions.

The application must treat prompts, archived answers, and retrieved source text as untrusted input. Such content must not be able to change reviewer identity, role permissions, or export authorization.

### Citation handling

The supplied dataset contains 2,439 citation occurrences.

A citation occurrence is not automatically a unique URL or an independently verified supporting source.

The implementation must define URL normalization and deduplication rules. It must also distinguish citation presence from verified claim support.

The same URL may occur inline, in a sources panel, or in multiple responses. Counts must state whether they refer to occurrences, unique normalized URLs, or unique sources per response.

## 7. Response Classification

Every supplied response must produce a structured result, an explicit failure, or an explicit skipped status.

The classification schema should include:

```json
{
  "response_id": "SOURCE_RESPONSE_ID",
  "engine": "SOURCE_ENGINE",
  "status": "success",
  "kasparro_absent": false,
  "kasparro_mentioned": true,
  "kasparro_recommended": false,
  "kasparro_negative": false,
  "competitors": [],
  "recommendation_position": null,
  "citation_ids": [],
  "evidence": [],
  "confidence": null,
  "failure_reason": null,
  "execution_mode": "replay",
  "classifier_version": "v1"
}
```

This is an illustrative schema. `SOURCE_RESPONSE_ID` and `SOURCE_ENGINE` must be populated from the actual dataset.

### Label definitions

- **Absent:** No identifiable mention of Kasparro in the response.
- **Mentioned:** Kasparro is explicitly referenced.
- **Recommended:** Kasparro is presented as a suitable option or provider.
- **Negative:** Kasparro is characterized unfavorably.
- **Competitors:** Explicitly named competing providers.
- **Recommendation position:** Position in a recommendation list when the order is observable.
- **Evidence:** Exact excerpts and their response locations supporting the labels.

Labels may overlap where justified. For example, a response could mention Kasparro while characterizing it negatively.

A failed classification is not equivalent to an absent mention. Failure and skip statuses must remain visible in the report.

### LLM usage

An LLM will be used for a substantive task such as semantic classification or diagnostic synthesis.

The classifier should:

1. Receive a constrained schema and a specific response.
2. Treat the archived response as untrusted data.
3. Return structured JSON.
4. Validate the output against the schema.
5. Retry only within a configured limit.
6. Record malformed output or provider failures.
7. Preserve the response ID and execution trace.
8. Avoid generating evidence that does not exist in the source response.

A deterministic replay adapter must be available when model credentials are unavailable.

## 8. Visibility Scoring

### Proposed scoring model

I propose a transparent visibility score from 0 to 100.

The score combines four components:

| Component | Weight |
|---|---:|
| Kasparro inclusion | 30% |
| Explicit recommendation | 40% |
| Recommendation prominence | 20% |
| Absence of negative characterization | 10% |
| **Total** | **100%** |

These weights are an initial design proposal, not an existing Kasparro production scoring model. They must be documented and versioned.

### Component definitions

**Inclusion**

- 1.0 when Kasparro is explicitly mentioned.
- 0.0 when Kasparro is absent from a successfully classified response.

**Recommendation**

- 1.0 when Kasparro is explicitly recommended.
- 0.0 when no recommendation is present.

**Prominence**

- Normalize observable recommendation position to a value between 0 and 1.
- Use a documented position-decay rule for ordered lists.
- Leave the component unknown when a reliable position cannot be established.

**Negative characterization**

- 1.0 when no negative characterization is identified.
- 0.0 when negative characterization is identified.

The negative-characterization component must be interpreted alongside the other components. It must not erase evidence of a negative result.

### Formula

For a response with all four components available:

```text
score = 100 * (
    0.30 * inclusion +
    0.40 * recommendation +
    0.20 * prominence +
    0.10 * non_negative
)
```

This formula is deterministic and easy to reproduce.

### Missing data and uncertainty

- A failed classification does not receive a score of zero.
- An unobservable recommendation position remains unknown.
- Missing components must not be silently treated as positive evidence.
- If a score cannot be calculated reliably, return an explicit unavailable status.
- Record component values, score version, classifier version, and evidence references.
- Report eligible, successful, failed, and skipped observations separately.

### Aggregation

Engine and category aggregates should use the same scoring version and clearly state their denominators.

For every aggregate, report:

- Number of eligible responses.
- Number successfully classified.
- Number failed.
- Number skipped.
- Mean score among successfully scored responses.
- Distribution of inclusion, recommendation, and negative labels.

Compare engines on the same prompts wherever possible. Do not imply that a score from this historical snapshot is a live ranking.

## 9. Prompt Categorization

Prompt categories should be inferred from the actual questions in `data/prompts.jsonl`.

Potential categories may include brand discovery, vendor comparison, capability evaluation, implementation questions, and purchase-intent questions, but these are candidate categories only.

The final category taxonomy must be based on the supplied prompts and documented with a category version.

The report should include category-level denominators and avoid presenting small samples as definitive trends.

## 10. Evidence-Backed Diagnostics

The final report must contain three important wins or losses.

Each diagnostic must distinguish:

1. The observed pattern.
2. The supporting evidence.
3. A possible explanation.
4. The evidence that would test that explanation.
5. The level of uncertainty.

Use the following structure for each diagnostic:

### Diagnostic 1: [Finding title]

**Observed pattern:**  
[Describe the measured pattern using actual dataset results.]

**Comparison:**  
[Compare engines or prompt categories using explicit denominators.]

**Evidence:**  
- Response ID: `[ACTUAL_RESPONSE_ID]`
- Engine: `[ACTUAL_ENGINE]`
- Prompt: `[ACTUAL_PROMPT]`
- Exact excerpt: `"[ACTUAL_SOURCE_EXCERPT]"`

**Possible explanation:**  
[State a hypothesis, not an established cause.]

**Validation needed:**  
[Explain what additional evidence would confirm or reject the hypothesis.]

**Confidence and limitations:**  
[Explain sample size, failures, ambiguity, and unverified citations.]

### Diagnostic 2: [Finding title]

**Observed pattern:**  
[Insert actual result.]

**Evidence:**  
[Insert response IDs and exact source excerpts.]

**Possible explanation:**  
[Insert a testable hypothesis.]

**Validation needed:**  
[Insert the next investigation.]

### Diagnostic 3: [Finding title]

**Observed pattern:**  
[Insert actual result.]

**Evidence:**  
[Insert response IDs and exact source excerpts.]

**Possible explanation:**  
[Insert a testable hypothesis.]

**Validation needed:**  
[Insert the next investigation.]

No diagnostic should be finalized until the actual source records have been analyzed.

## 11. Prioritized Remedies

The report must contain three remedies supported by the diagnostics.

A remedy can be an investigation when the evidence is insufficient to justify a direct change.

### Remedy 1: [Highest-priority action]

**Problem:**  
[Describe the demonstrated problem.]

**Supporting evidence:**  
[Reference diagnostic and response IDs.]

**Action:**  
[Describe the proposed action or investigation.]

**Expected benefit:**  
[Describe the intended outcome without promising a ranking improvement.]

**Effort:**  
[Low, medium, or high, with a short justification.]

**Uncertainty:**  
[Describe what remains unverified.]

**Validation:**  
[Define a measurable success criterion, baseline, and evaluation period.]

### Remedy 2: [Second-priority action]

**Problem:** [Evidence-backed problem.]

**Action:** [Proposed investigation or change.]

**Expected benefit:** [Expected outcome.]

**Effort:** [Estimated effort.]

**Uncertainty:** [Remaining unknowns.]

**Validation:** [Measurable test.]

### Remedy 3: [Third-priority action]

**Problem:** [Evidence-backed problem.]

**Action:** [Proposed investigation or change.]

**Expected benefit:** [Expected outcome.]

**Effort:** [Estimated effort.]

**Uncertainty:** [Remaining unknowns.]

**Validation:** [Measurable test.]

Remedies must not invent company facts or promise improvements unsupported by evidence.

## 12. Backend API

The backend exposes the following endpoints.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/datasets` | Import and validate input data |
| POST | `/analyses` | Start an analysis |
| GET | `/analyses/{id}` | Inspect analysis status and results |
| PATCH | `/reports/{id}` | Edit an editable draft |
| POST | `/reports/{id}/submit` | Freeze and submit a report version |
| POST | `/reports/{id}/decision` | Approve or reject the submitted version |
| GET | `/reports/{id}/export` | Export an eligible approved version |

FastAPI's generated documentation should be available at `/docs` when the application is running.

### Import request

```json
{
  "dataset_name": "kasparro-historical-snapshot",
  "source_directory": "data"
}
```

The server must validate the imported files and return import counts and validation errors.

### Analysis request

```json
{
  "dataset_id": "DATASET_ID",
  "execution_mode": "replay",
  "classifier_version": "v1",
  "scoring_version": "v1"
}
```

The actual identifiers must come from the application.

### Draft editing request

```json
{
  "title": "AI visibility analysis",
  "diagnostics": [],
  "remedies": []
}
```

Draft changes must be validated and persisted. Editing a submitted or approved version must create a new draft rather than modifying the immutable historical version.

### Review decision request

```json
{
  "version_id": "REPORT_VERSION_ID",
  "decision": "approve",
  "comment": "Evidence and remedies reviewed."
}
```

The backend derives the reviewer identity from authentication configuration. The request body cannot grant reviewer privileges.

### Export behavior

Export must:

- Require an authenticated analyst or reviewer with appropriate export permission.
- Identify the exact report version being exported.
- Reject drafts.
- Reject rejected versions.
- Reject stale content.
- Permit only an approved immutable version.
- Preserve the version's findings, evidence, remedies, and review decision.
- Return a suitable HTTP error when export is not permitted.

An older approval may authorize export of that exact older immutable version, but it must never authorize export of newer unreviewed content.

## 13. Database Design

SQLite is sufficient for the assignment.

Suggested entities:

### Dataset

- `id`
- `name`
- `source_hash`
- `created_at`
- `validation_status`

### Response

- `id`
- `dataset_id`
- `source_response_id`
- `prompt_id`
- `engine`
- `raw_payload`
- `imported_at`

The source response identifier should be unique within the appropriate dataset scope.

### AnalysisRun

- `id`
- `dataset_id`
- `execution_mode`
- `classifier_version`
- `scoring_version`
- `status`
- `started_at`
- `completed_at`
- `configuration_json`

### ResponseResult

- `id`
- `analysis_id`
- `response_id`
- `status`
- `labels_json`
- `components_json`
- `score`
- `evidence_json`
- `failure_reason`

### Report

- `id`
- `dataset_id`
- `current_draft_version_id`
- `created_at`

### ReportVersion

- `id`
- `report_id`
- `version_number`
- `status`
- `content_json`
- `content_hash`
- `created_by`
- `created_at`
- `submitted_at`

### ReviewDecision

- `id`
- `report_version_id`
- `reviewer_id`
- `decision`
- `comment`
- `created_at`

Use foreign keys and appropriate uniqueness constraints. Persist review history instead of overwriting previous decisions.

## 14. Human Review and Authorization

The system uses two configured local identities or tokens.

### Analyst

Can:

- Import datasets.
- Run analyses.
- Inspect analysis results.
- Create and edit drafts.
- Submit report versions for review.

Cannot approve or reject reports unless separately authorized as a reviewer.

### Reviewer

Can:

- Inspect submitted report versions.
- Approve a submitted version.
- Reject a submitted version with a comment.

The application must derive identity and permissions from backend configuration, not from caller-supplied role names or actor fields.

### Report lifecycle

```text
DRAFT
  |
  v
SUBMITTED
  |
  +------> APPROVED
  |
  +------> REJECTED
```

After editing an approved or submitted report, the application creates a new draft version. That new version must be submitted and reviewed independently.

The submitted version is immutable. Its findings, evidence, remedies, and version identifier remain unchanged after submission.

### Required authorization demonstrations

1. An analyst attempts a reviewer-only decision and receives an authorization error.
2. A rejected report cannot be exported.
3. An approved report can be exported.
4. Editing an approved report creates a new draft.
5. The new draft cannot be exported until it is reviewed.
6. The old approved version remains identifiable and immutable.

### Future improvements

A production deployment should consider approval expiry, stronger credential management, concurrent editing protection, and explicit reviewer conflict-of-interest rules.

These are documented future improvements, not claimed as implemented features.

## 15. Reliability and Execution Controls

The implementation should include:

- Request validation.
- Model-output validation.
- Bounded timeouts and retries.
- Maximum output sizes.
- Explicit provider-error handling.
- Traceable response IDs.
- Execution-mode labels.
- Configuration and version tracking.
- Structured error responses.
- Environment-based secrets.
- Idempotent imports.
- Per-record failure isolation.

A provider timeout or malformed model response must not become a confident classification.

A bounded synchronous execution flow is acceptable for this assignment. Its request-duration and scalability limitations must be documented.

### Example environment configuration

`.env.example`:

```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./kasparro.db
EXECUTION_MODE=replay

ANALYST_TOKEN=replace-with-local-analyst-token
REVIEWER_TOKEN=replace-with-local-reviewer-token

LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=20
LLM_MAX_RETRIES=2
```

Do not commit real credentials or private tokens.

## 16. Evaluation Strategy

Evaluation must be separate from the application engineering tests.

### Manual labeling

Before tuning the classifier, manually label at least eight supplied responses covering:

- All three AI engines.
- Several prompt categories.
- Present and absent Kasparro mentions.
- Recommendation cases.
- Negative characterization cases.
- Citation cases where available.

Add two clearly marked synthetic edge cases of your own.

The edge cases must be distinguished from supplied data and must not be counted as actual provider observations.

Record the selection rationale and preserve a versioned expected-label dataset.

### Evaluation fields

Each evaluation case should contain:

```json
{
  "case_id": "CASE_ID",
  "source_type": "supplied",
  "response_id": "SOURCE_RESPONSE_ID",
  "expected": {
    "kasparro_mentioned": true,
    "kasparro_recommended": false,
    "kasparro_negative": false
  },
  "expected_evidence": [],
  "notes": "Human-reviewed expected labels."
}
```

For synthetic cases, use `"source_type": "synthetic"` and document their purpose.

### Classification metrics

For each label, calculate precision and recall where the evaluation data supports the calculation.

```text
precision = true_positives / (true_positives + false_positives)

recall = true_positives / (true_positives + false_negatives)
```

If a denominator is zero, report the metric as undefined rather than silently returning a perfect score.

Also report exact-match agreement or per-label agreement, as appropriate for the dataset.

### Deterministic score verification

Independently test the scoring formula using known component values and expected outputs.

This tests the scoring implementation, not the quality of the LLM's semantic classifications.

### Rule-based baseline

Implement a simple baseline using deterministic text matching and explicit rules.

Run both the baseline and the proposed approach on the same evaluation cases.

Report:

- Per-label precision.
- Per-label recall.
- Agreement.
- Score-calculation correctness.
- Successful analyses.
- Failed analyses.
- Skipped analyses.
- Evidence-validation failures.

### Diagnostic and remedy validation

Check whether:

- Each diagnostic is supported by source response evidence.
- Each cited response ID exists.
- Each quoted excerpt appears in the source.
- Each remedy follows logically from its diagnostic.
- Unsupported claims are identified.
- An incorrect-evidence fixture is rejected or flagged.

An LLM judging its own generated prose is not sufficient evidence of correctness.

### Failure, diagnosis, fix, and regression

The evaluation report must document one actual failure.

Use this structure:

**Failure:** [Describe the observed failure.]

**Diagnosis:** [Explain the cause using logs, output, or a controlled fixture.]

**Change:** [Describe the implemented correction.]

**Regression case:** [Identify the test that prevents recurrence.]

**Verification:** [Record the actual command and observed result.]

Do not claim that a failure was fixed until the regression test has been run.

## 17. Required Automated Tests

The test suite must include:

| Test | Expected behavior |
|---|---|
| Invalid input | Reject malformed records or record them as invalid without corrupting valid records |
| Duplicate response | Reject or safely reuse an existing identified response |
| Model timeout | Record failure without manufacturing a result |
| Malformed model output | Validate, retry within limits, or record an explicit failure |
| Wrong reviewer role | Deny the decision request |
| Rejected report export | Refuse export |
| Edit after approval | Create a new draft requiring fresh review |
| Approved report export | Export the exact approved immutable version |
| Unsupported evidence | Flag or reject the unsupported claim |
| Deterministic scoring | Match expected component and aggregate calculations |

Use deterministic model stubs for engineering tests. Clearly distinguish those results from real-model quality evaluation.

## 18. Reproducibility and Commands

The following commands are intended for the completed implementation. Confirm that the corresponding files and scripts exist before claiming they have run successfully.

### Verify the supplied pack

From the extracted assignment directory:

```bash
python3 tools/check_pack.py
```

On Windows:

```powershell
py -3 tools/check_pack.py
```

Read `data/READ_ME.txt` before implementing the data contract.

### Create an environment

```bash
python3 -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Initialize the database

```bash
python -m app.database
```

This command must be implemented to initialize the SQLite schema.

### Start the application

```bash
uvicorn app.main:app --reload
```

### Check health and API documentation

```bash
curl http://127.0.0.1:8000/health
```

Open:

```text
http://127.0.0.1:8000/docs
```

### Run tests

```bash
pytest -q
```

### Run evaluation

```bash
python -m evaluation.run_eval
```

The evaluation command must write a readable comparison report containing the baseline and proposed approach, metrics, failure counts, and execution mode.

### Replay mode

Replay mode must work without a model API key.

All replay results and traces must explicitly identify their execution mode.

### Real-model mode

The real-model adapter must be implemented and documented, even if credentials are unavailable during development.

Document the provider, model, configuration, number of calls, execution time, and available cost measurements for any real-model evaluation.

Do not fabricate model usage or performance measurements.

## 19. Final Analysis Report

The final analysis output should be provided as JSON or another readable machine-readable format.

It must contain:

- Dataset and run provenance.
- Prompt and response coverage.
- Engine-level scores.
- Category-level scores.
- Label distributions.
- Eligible, successful, failed, and skipped counts.
- Three evidence-backed diagnostics.
- Three prioritized remedies.
- Score and classifier versions.
- Execution mode.
- Evaluation results.
- Limitations and uncertainty.

### Dataset summary

Complete using the actual execution output:

| Metric | Actual result |
|---|---|
| Supplied prompts | 50, as specified by the assignment brief |
| Supplied archived responses | 150, as specified by the assignment brief |
| Supplied citation occurrences | 2,439, as specified by the assignment brief |
| Successfully analyzed responses | [ACTUAL RESULT] |
| Failed responses | [ACTUAL RESULT] |
| Skipped responses | [ACTUAL RESULT] |
| Successfully scored responses | [ACTUAL RESULT] |
| Execution mode | [ACTUAL MODE] |
| Active time spent | [ACTUAL TIME] |

The supplied counts describe the assignment pack. They are not proof that the implementation imported or processed every record successfully.

## 20. Decision Note

### Scoring and aggregation

The proposed score combines inclusion, recommendation, recommendation prominence, and negative characterization. Weights and scoring rules are explicit and versioned.

Unknown values remain unknown, and failed analyses are excluded from successful-score denominators while being reported separately.

Engine comparisons use matching prompts wherever possible. Aggregates include denominators and failure counts.

### Backend and review design

The application separates ingestion, classification, scoring, storage, API operations, and report review.

SQLite provides sufficient persistence for the assignment. FastAPI provides validated endpoints and API documentation.

Analyst and reviewer permissions are enforced by the backend. Submitting a report freezes its version, and export is permitted only for the exact approved immutable version.

### Reliability choices

The system validates input and output, limits retries, records provider failures, and preserves response-level traceability.

Replay mode allows the application and evaluation mechanics to be tested without external credentials. Replay mode does not establish real-model correctness, latency, cost, or variability.

### Alternatives considered

- **SQLite versus a server database:** SQLite is sufficient for a small local assignment; a server database would be more suitable for concurrent production workloads.
- **Synchronous versus asynchronous processing:** A bounded synchronous workflow reduces implementation complexity; asynchronous workers would be appropriate for larger datasets and longer model calls.
- **Rule-based versus LLM classification:** Rules are predictable but may miss semantic nuance. LLM classification can handle ambiguity but requires schema validation and evaluation.
- **Automatic versus human-controlled publication:** Human approval adds a step but prevents unreviewed findings from being exported.

### Top remedy

[Insert the highest-priority remedy from the actual evidence-backed findings. Explain the evidence, expected benefit, uncertainty, and validation plan.]

### Largest risk

The largest risk is drawing conclusions from incomplete or ambiguous classification results or from a small historical sample. Citation presence alone does not establish source support, and the historical snapshot does not prove current AI visibility.

### Unfinished work and omissions

[Record all unfinished work, unimplemented requirements, evaluation limitations, and deliberate omissions.]

### Questions before release

- Are the proposed scoring weights appropriate for the intended business decision?
- Which categories and engines should receive greater attention in future runs?
- What evidence standard is required before a citation is considered supportive?
- What review-expiry and concurrency rules should apply in production?
- What additional evaluation data is required before making stronger claims?

### AI assistance disclosure

[Describe the AI coding assistants or models used, the tasks for which they were used, the code and outputs manually verified, and any limitations. Include actual model and configuration details where available.]

## 21. Active-Time Log

The assignment specifies a six-active-hour limit.

Record actual active work. Do not count unperformed work as completed.

| Activity | Actual time | Status |
|---|---|---|
| Read assignment and inspect data | [TIME] | [STATUS] |
| Implement ingestion and validation | [TIME] | [STATUS] |
| Implement classification and scoring | [TIME] | [STATUS] |
| Implement APIs and persistence | [TIME] | [STATUS] |
| Implement review and export controls | [TIME] | [STATUS] |
| Implement evaluation and tests | [TIME] | [STATUS] |
| Write documentation and decision note | [TIME] | [STATUS] |
| **Total active time** | **[ACTUAL TOTAL]** | |

Stop when six active hours have been reached. Disclose remaining work.

## 22. Submission Checklist

Before submitting, verify the following:

- [ ] Source code is included in a private repository or archive.
- [ ] Database initialization is included.
- [ ] Dependency versions are recorded.
- [ ] `.env.example` is included without real secrets.
- [ ] The supplied data and private outputs are not exposed in public Git history.
- [ ] Input validation and duplicate handling are tested.
- [ ] Replay mode works without model credentials.
- [ ] The real-model adapter and switching instructions are documented.
- [ ] Every response has a result, failure, or skipped reason.
- [ ] The scoring formula and uncertainty handling are documented.
- [ ] At least eight supplied responses have been manually labeled.
- [ ] Two synthetic edge cases are clearly identified.
- [ ] The rule-based baseline and proposed approach are compared.
- [ ] A failure, diagnosis, fix, and regression test are documented.
- [ ] Wrong-role denial is demonstrated.
- [ ] Rejected report export is blocked.
- [ ] Edit-after-approval creates a new draft.
- [ ] Only an approved immutable version can be exported.
- [ ] Three evidence-backed diagnostics are included.
- [ ] Three prioritized remedies are included.
- [ ] The active-time log and omissions are complete.
- [ ] AI assistance is disclosed.
- [ ] Setup, test, evaluation, and example API commands are documented.
- [ ] The final output has been checked against the actual assignment data.

Submit the private archive or private repository by replying to the email that supplied the assignment pack. Grant access to the sender and any reviewers named in the invitation. If links cannot be shared, attach an archive.

Do not contact customers, publish findings, execute remedies, or change a real website. Report missing files or access blockers to the hiring team.

---

**Final status:** This document defines the proposed implementation and reporting approach. The project should be marked complete only after the code, tests, evaluation, actual dataset findings, and report-review workflow have been implemented and verified.