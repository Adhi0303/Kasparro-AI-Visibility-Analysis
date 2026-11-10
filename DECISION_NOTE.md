# Decision Note: Kasparro AI Visibility Analysis & Human Review

**Pack Track:** Fresher AI Engineer I  
**Pack Version:** 1.0.0  
**Snapshot Date:** 31 July 2026 (Historical capture via DataForSEO, India, English)  
**Author:** ADARSH S 
**Date:** 28 October 2026  

---

## 1. Scoring & Aggregation Decisions

### Scoring Formula (v1)
$$\text{score} = 100 \times (0.30 \times \text{inclusion} + 0.40 \times \text{recommendation} + 0.20 \times \text{prominence} + 0.10 \times \text{non\_negative})$$

1. **Inclusion (30%):** Measures whether the brand entered the model's awareness/consideration set (1.0 if mentioned, 0.0 if absent).
2. **Recommendation (40%):** Weighted highest because being mentioned merely as a passing comment or in a list of dubious vendors does not drive business value. Only explicit recommendations receive 1.0.
3. **Prominence (20%):** Evaluates placement order in numbered recommendations via reciprocal decay ($1 / \text{rank}$). When order is unobservable in prose, prominence is left `null` and available weights are normalized over 0.80 to maintain a standard 0–100 scale without fabricating artificial ranks.
4. **Non-Negative Characterization (10%):** Evaluates absence of explicit warnings, ScamAdviser citations, or caution statements. Scored 1.0 if clean, 0.0 if negative.

### Handling Failures & Denominators
- Failed or skipped classifications are **never** scored as 0.0; they receive `score = null` and `status = unavailable`.
- Aggregate denominators clearly report:
  - **Eligible responses:** 150
  - **Successfully scored responses:** 150
  - **Failed responses:** 0
  - **Skipped responses:** 0

---

## 2. Backend & Review Architecture

### Role-Based Access Control
- Authentication uses static Bearer tokens mapped in server configuration (`ANALYST_TOKEN` and `REVIEWER_TOKEN`).
- Permissions are strictly derived on the backend via FastAPI dependencies (`require_analyst`, `require_reviewer`).
- Request body attributes cannot alter or spoof actor permissions. Analysts attempting review decisions receive HTTP 403 Forbidden.

### Immutability & Report Lifecycle
```
DRAFT ──► SUBMITTED ──► APPROVED ──► (Export Permitted)
                    └──► REJECTED ──► (Export Blocked)
```
- Submitting a report freezes its state (`SUBMITTED`) and records a SHA-256 content hash.
- Any subsequent edit by an Analyst does not mutate historical versions; it automatically creates a new `DRAFT` (version $N+1$).
- The export gate strictly checks status: drafts, rejected reports, and unreviewed versions return HTTP 400. Only the exact approved version can be exported.

---

## 3. Reliability & Technology Choices

| Component | Choice | Justification |
|---|---|---|
| Framework | **FastAPI** | Auto-generated OpenAPI `/docs`, strong Pydantic typing, native async support. |
| Persistence | **SQLite** | Zero-configuration file-based DB, adequate for the assignment's local snapshot scope. |
| Validation | **Pydantic v2** | Strict schema validation for incoming JSON and database payloads. |
| LLM Abstraction | **Adapter Pattern** | Separates interface (`LLMBase`) from implementation (`ReplayClassifier`, `ProviderClassifier`). |
| Ingestion | **SHA-256 + Deduplication** | Verifies input integrity and ensures idempotent imports. |

### Alternatives Considered
- **PostgreSQL vs. SQLite:** SQLite was chosen because the assignment is an offline/local single-machine evaluation. PostgreSQL would add unnecessary operational overhead without improving analytical outcomes.
- **Asynchronous Task Queue (Celery/Redis) vs. In-process Runner:** With 150 local records, in-process bounded synchronous execution completes in under 5 seconds in replay mode, avoiding external dependencies like Redis.
- **Always-on Live API vs. Replay Mode:** Replay mode provides 100% deterministic reproducibility for grading and automated tests without incurring external API costs.

### Documented Failure, Diagnosis, Fix, and Regression
As required by the assignment brief, one critical failure observed during development is documented:
- **Failure:** Diagnostic findings initially contained paraphrased summaries of competitor recommendations (e.g. *"Profound, Peec AI, and Otterly are dedicated platforms..."*) rather than exact substring matches from `responses.jsonl`.
- **Diagnosis:** LLM-generated summaries were transcribed into diagnostic data fixtures without automated substring verification against source `answer_text` records.
- **Fix:** Replaced all excerpts with verified verbatim substrings from the source responses and added an automated regression test (`test_all_diagnostic_evidence_verbatim_integrity`) in `tests/test_analysis.py` that asserts `excerpt in answer_text` across all diagnostics.
- **Verification:** Command `pytest tests/test_analysis.py -k test_all_diagnostic_evidence_verbatim_integrity` passed with 100% string-matching.

---

## 4. Key Empirical Findings (Actual Dataset)

From the analysis of the 150 archived responses:

| AI Engine | Eligible Responses | Mean Score | Inclusion Rate | Recommendation Rate | Negative Rate |
|---|:---:|:---:|:---:|:---:|:---:|
| **Google AI Mode** | 50 | **34.75** | 50.0% | 8.0% | 4.0% |
| **ChatGPT** | 50 | **36.48** | 50.0% | 14.0% | **12.0%** |
| **Gemini** | 50 | **41.48** | 44.0% | **26.0%** | 2.0% |
| **Overall** | **150** | **37.57** | **48.0%** | **16.0%** | **6.0%** |

### Top Evidence-Backed Remedy
**Action:** Publish 3 Verified Third-Party B2B Case Studies with Before/After GEO Metrics.  
**Supporting Evidence:** ChatGPT answers directly cite ScamAdviser and flag Kasparro for lacking independent evidence (Response `ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc`).  
**Expected Benefit:** Replaces cautionary third-party citations with verified proof points, resolving the 12% negative sentiment in ChatGPT.  
**Validation Plan:** Track ChatGPT answers across prompts 001–005 over a 30-day monitoring window. Target: 0 ScamAdviser citations.

---

## 5. Largest Risk & Limitations

1. **Historical Snapshot Scope:** The data reflects a single capture on 31 July 2026. Models and web retrieval indices evolve rapidly; this report documents historical snapshot visibility, not live 2026 rankings.
2. **Citations vs. Claim Verification:** Citations record URLs linked in AI responses (2,439 occurrences). A citation does not prove that the underlying webpage supports the model's claim without external page inspection.
3. **Small Sample Size for Category Generalization:** While 150 responses is sufficient for this assignment, enterprise deployment would require 1,000+ prompts run repeatedly across multiple geographic locations.

---

## 6. AI Assistance Disclosure

- **Tools Used:** Antigravity AI Coding Assistant.
- **Tasks Delegated:** Boilerplate FastAPI schema generation, SQLite schema creation, and regex pattern drafting.
- **Human Verification:** All business logic, scoring formulas, permission guards, database queries, and diagnostic findings were manually reviewed, verified with automated pytest suites, and checked against the assignment specification.

---

## 7. Active-Time Log

| Activity | Time Spent | Status |
|---|:---:|:---:|
| Assignment reading, brief inspection & pack check | 40 mins | Completed |
| Schema design, models, and SQLite persistence | 45 mins | Completed |
| Data ingestion pipeline & SHA-256 validation | 35 mins | Completed |
| Replay classifier, provider adapter & error handling | 45 mins | Completed |
| Scoring formula, prominence decay & category taxonomy | 40 mins | Completed |
| Report lifecycle, review workflow & export gate | 40 mins | Completed |
| Automated pytest suite (21 tests) | 35 mins | Completed |
| Evaluation grader, cases & comparison report | 30 mins | Completed |
| Final report generation, README & Decision Note | 35 mins | Completed |
| **Total Active Time** | **5h 45m** | **Within 6h Limit** |

---

## 8. Unfinished Work & Deliberate Omissions

- **OAuth 2.0 / JWT Authentication:** Omitted per brief; static local tokens adequately demonstrate permission isolation.
- **Live Search Crawling:** Live queries against ChatGPT or Google were omitted to comply with offline snapshot guidelines.
- **Distributed Job Workers:** Handled synchronously in-process given the small dataset scale (150 responses).

