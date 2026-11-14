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
  - **Eligible responses:** 150 (50 per engine: Google AI Mode, ChatGPT, Gemini)
  - **Successfully scored responses:** 150 (100% complete)
  - **Failed responses:** 0
  - **Skipped responses:** 0
- Response-accounting audit confirmed: exactly 50 prompts, 150 archived responses, exactly 150 unique UUIDs, 0 duplicate/missing response IDs, and 150 successful scores forming the canonical scoring denominator.

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
- **End-to-End Evidence Integrity Audit (P3):** Audited all 6 evidence citations across the 3 final diagnostics against the original 150-response archive. Confirmed 6/6 exact verbatim matches, 0 offset mismatches, 0 invalid response IDs, and centralized canonical slicing via `_audit_evidence_candidates` ensuring fabricated or altered quotations are rejected.

---

## 4. Key Empirical Findings (Actual Dataset)

From the analysis of the 150 archived responses:

| AI Engine | Eligible Responses | Mean Score | Inclusion Rate | Recommendation Rate | Negative Rate |
|---|:---:|:---:|:---:|:---:|:---:|
| **Google AI Mode** | 50 | **32.75** | 50.0% | 4.0% | 4.0% |
| **ChatGPT** | 50 | **31.43** | 50.0% | 2.0% | **6.0%** |
| **Gemini** | 50 | **34.93** | 44.0% | **12.0%** | 0.0% |
| **Overall** | **150** | **33.04** | **48.0%** | **6.0%** | **3.33%** |

### Verified Prioritized Remedies

1. **Remedy 1 (Top Remedy): Publish Verified Third-Party Case Studies with Before/After GEO Metrics**
   - **Problem Addressed:** Negative or cautionary characterization reached 6.0% on ChatGPT, with citations explicitly noting a lack of verified independent evidence (Diagnostic 2).
   - **Supporting Evidence:** Responses `ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc`, `5492b420-7fa5-4de4-ab2c-6c4412e5b18d`, `08f81acc-0824-4e3a-a5d5-58446e2a6a90`.
   - **Recommended Action:** Produce and publish 3 detailed customer case studies on independent third-party platforms with verifiable before-and-after AI visibility metrics.
   - **Expected Benefit:** Displaces cautionary ScamAdviser citations with verifiable proof points, reducing ChatGPT negative characterization.
   - **Effort:** Medium (Customer approvals and content packaging).
   - **Uncertainty:** Search index ingestion cycles vary across crawlers.
   - **Measurable Validation:** Re-evaluate branded trust prompts after publication; target: 0 ScamAdviser citations.

2. **Remedy 2: Establish Official Profiles on Software Review Directories (G2, Capterra, ProductHunt)**
   - **Problem Addressed:** Kasparro appeared in 0/75 unbranded category discovery queries, whereas competitors (Profound, Peec AI, Otterly) were consistently recommended from directory citations (Diagnostic 1).
   - **Supporting Evidence:** Responses `0f38b477-9f3c-44a8-9d10-0b6016db6150`, `11010066-8ed2-4741-856e-9259ae1a377b`.
   - **Recommended Action:** Claim and populate verified vendor profiles under AI Search Optimization and collect verified customer reviews.
   - **Expected Benefit:** Directly increases unbranded discovery inclusion by establishing directory entity presence.
   - **Effort:** Low (Profile creation and customer review collection).
   - **Uncertainty:** Review directory verification requires minimum review thresholds.
   - **Measurable Validation:** Re-run unbranded discovery prompts; track change in unbranded inclusion rate.

3. **Remedy 3: Implement Organization Schema.org Markup & Brand Disambiguation from 'Kaspr'**
   - **Problem Addressed:** Phonetic entity overlap with 'Kaspr' and 'Gaspar AI' appeared in 20 responses/citations, splitting brand attribution (Diagnostic 3).
   - **Supporting Evidence:** Responses `136b8240-008c-46ff-b744-592c4d859e98`, `1d2dc007-0757-480d-a086-6b6e2e13c463`.
   - **Recommended Action:** Deploy JSON-LD Organization schema on kasparro.com with explicit `sameAs` links and publish an entity clarification page distinguishing Kasparro (AISO) from Kaspr (B2B contact data).
   - **Expected Benefit:** Clarifies entity resolution for knowledge graph crawlers and resolves name collisions.
   - **Effort:** Low (Technical schema markup deployment).
   - **Uncertainty:** Knowledge graph updates propagate over multiple crawl cycles.
   - **Measurable Validation:** Verify Google Rich Results validation passes; monitor disambiguation citations.

### Clean Execution Mode Separation

The assignment architecture enforces strict boundaries between data tiers to prevent conflating replay results with live LLM accuracy:

| Execution Tier | Scope / Dataset | Classifier Engine | Primary Outputs & Metrics |
|---|---|---|---|
| **1. Historical Snapshot** | 150 archived responses (31 July 2026) | Static Dataset / Replay | Overall score: 33.04; Inclusion: 48.0%; Rec: 6.0%; Neg: 3.33% (`final_report.json`, `report.html`) |
| **2. Deterministic Replay** | 20 regression + 30 held-out cases | Regex / Rule-based (v1) | Regression: 100.0% agreement; Held-out: 63.3% agreement (`eval_results.json`, `eval_held_out_results.json`) |
| **3. Real-Model Provider** | 20 regression cases + 60 repeatability calls | Live Gemini API (`gemini-3.5-flash-lite`) | Single pass: 72.2% matched-subset agreement (13/18), +27.8 percentage points over the 44.4% baseline; 90.0% execution coverage (18/20), with 2 HTTP 429 quota failures; coverage-adjusted agreement: 65.0% (13/20). Repeatability: 88.89% stability among 18 repeatable cases, 90.0% call coverage (54/60), with 6 quota failures (`eval_provider_results.json`, `repeatability_regression.json`) |

*For complete reconciliation audit details, see [`docs/P4_FINAL_ANALYSIS_AUDIT.md`](docs/P4_FINAL_ANALYSIS_AUDIT.md).*

---

## 5. Largest Risk & Limitations

1. **Historical Snapshot Scope:** The data reflects a single capture on 31 July 2026. Models and web retrieval indices evolve rapidly; this report documents historical snapshot visibility, not live 2026 rankings.
2. **Citations vs. Claim Verification:** Citations record URLs linked in AI responses (2,439 occurrences). A citation does not prove that the underlying webpage supports the model's claim without external page inspection.
3. **Small Sample Size for Category Generalization:** While 150 responses is sufficient for this assignment, enterprise deployment would require 1,000+ prompts run repeatedly across multiple geographic locations.

---

## 6. AI Assistance Disclosure

- **Tools Used:** Antigravity AI Coding Assistant and ChatGPT.
- **AI-Assisted Work:** Implementation support across backend scaffolding and application modules; prompt and classifier iteration; test-case development; evaluation-runner and report-generation support; evidence-integrity checks; and documentation drafting and revision.
- **Candidate Review and Verification:** The candidate directed the implementation, reviewed and revised generated code, checked design decisions against the assignment requirements, inspected evaluation outputs and evidence, and ran the automated test suite and pack-integrity checker. AI-generated code and analysis were treated as proposals and were not accepted without review and verification.

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
| Automated pytest suite (actual test counts are reported by the current pytest/CI run) | 35 mins | Completed |
| Regression/held-out evaluation grader, cases & comparison reports | 30 mins | Completed |
| Data-driven report generation, README & Decision Note | 35 mins | Completed |
| **Total Active Time** | **5h 45m** | **Within 6h Limit** |

---

## 8. Unfinished Work & Deliberate Omissions

- **OAuth 2.0 / JWT Authentication:** Omitted per brief; static local tokens adequately demonstrate permission isolation.
- **Live Search Crawling:** Live queries against ChatGPT or Google were omitted to comply with offline snapshot guidelines.
- **Distributed Job Workers:** Handled synchronously in-process given the small dataset scale (150 responses).

