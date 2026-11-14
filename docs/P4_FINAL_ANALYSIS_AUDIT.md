# P4 — Final Analysis and Reporting Audit Report

**Date:** 2026-11-14  
**Audit Status:** PASSED (100% Reconciled)  
**Execution Context:** Verification of 150 archived responses, deterministic replay evaluation, live Gemini provider results, and analytical reporting artifacts.

---

## 1. Response-Accounting Table (P4.1)

Every response record from `data/responses.jsonl` was traced to prompt-level records in `prompt_scores.json` and database analysis execution.

| Engine | Archived Responses | In Analysis Scores | Successful Responses | Explicitly Failed | Skipped | Status |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Google AI Mode (`aimode`)** | 50 | 50 | 50 | 0 | 0 | 100% Reconciled |
| **OpenAI ChatGPT (`chatgpt`)** | 50 | 50 | 50 | 0 | 0 | 100% Reconciled |
| **Google Gemini (`gemini`)** | 50 | 50 | 50 | 0 | 0 | 100% Reconciled |
| **TOTAL** | **150** | **150** | **150** | **0** | **0** | **100% Complete** |

- **Total Prompts:** 50 (from `data/prompts.jsonl`).
- **Total Citations:** 2,439 entries.
- **Unique Response IDs:** Exactly 150 unique UUIDs; 0 duplicate response IDs; 0 missing response IDs.
- **Denominator Integrity:** 150 successful responses form the valid denominator for all global scoring calculations. No artificial successes or zero-score fills were manufactured.

---

## 2. Recalculated Aggregates vs. Canonical Reports (P4.2)

All visibility scores and rates were independently computed from the underlying response-level records and compared against `evaluation/results/final_report.json`, `prompt_scores.json`, and `report.html`.

### Overall Metrics

| Metric | Independently Calculated | Canonical Final Report | In Dashboard HTML | Reconciliation Status |
|---|:---:|:---:|:---:|:---:|
| **Mean Visibility Score** | **33.04** (raw: 33.0389) | 33.04 | 33.04 | Exact Match |
| **Inclusion / Mention Rate** | **48.0%** (72/150) | 0.48 (48.0%) | 48.0% | Exact Match |
| **Recommendation Rate** | **6.0%** (9/150) | 0.06 (6.0%) | 6.0% | Exact Match |
| **Negative Characterization Rate** | **3.33%** (5/150) | 0.0333 (3.3%) | 3.3% | Exact Match |

### Engine Aggregates

| Engine | Calculated Mean | Report Mean | Calculated Inclusion | Report Inclusion | Calculated Rec. | Report Rec. | Calculated Neg. | Report Neg. |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Google AI Mode** | 32.75 | 32.75 | 50.0% (25/50) | 0.50 | 4.0% (2/50) | 0.04 | 4.0% (2/50) | 0.04 |
| **OpenAI ChatGPT** | 31.43 | 31.43 | 50.0% (25/50) | 0.50 | 2.0% (1/50) | 0.02 | 6.0% (3/50) | 0.06 |
| **Google Gemini** | 34.93 | 34.93 | 44.0% (22/50) | 0.44 | 12.0% (6/50) | 0.12 | 0.0% (0/50) | 0.00 |

### Category Aggregates (Taxonomy v1)

| Category | Eligible Responses | Mean Score | Inclusion Rate | Recommendation Rate | Negative Rate |
|---|:---:|:---:|:---:|:---:|:---:|
| **Brand Discovery** | 36 | 22.57 | 25.0% (9/36) | 2.78% (1/36) | 5.56% (2/36) |
| **Vendor Comparison** | 24 | 44.65 | 75.0% (18/24) | 8.33% (2/24) | 0.00% (0/24) |
| **Capability Evaluation** | 30 | 29.17 | 40.0% (12/30) | 3.33% (1/30) | 0.00% (0/30) |
| **Trust & Legitimacy** | 27 | 38.30 | 62.96% (17/27) | 7.41% (2/27) | 11.11% (3/27) |
| **Pricing & Implementation** | 33 | 35.23 | 48.48% (16/33) | 9.09% (3/33) | 0.00% (0/33) |

**Result:** Zero mathematical discrepancies detected across all 150 responses, 3 engines, and 5 prompt categories.

---

## 3. Verification of Final Diagnostics (P4.3)

All three diagnostics in `final_report.json` and `report.html` are supported by verifiable, grounded response records:

1. **Diagnostic 1: Absence in Unbranded Category Discovery Prompts**
   - **Observed Pattern:** Kasparro included in 0/75 unbranded responses (0.0%), while competitors (Profound, Peec AI, Otterly) dominated recommendations.
   - **Supporting Citations:** Verified against `0f38b477-9f3c-44a8-9d10-0b6016db6150` (`[762:818]`) and `11010066-8ed2-4741-856e-9259ae1a377b` (`[1445:1755]`).
   - **Honest Boundary:** Factual observation of absence in category discovery; distinguished from hypotheses about crawler indexing.

2. **Diagnostic 2: Third-Party Evidence Deficit and Cautionary Characterization**
   - **Observed Pattern:** Negative or cautionary characterization was highest on ChatGPT (6.0% (3/50)), alongside 5 responses citing ScamAdviser or highlighting missing independent case studies.
   - **Supporting Citations:** Verified against `5492b420-7fa5-4de4-ab2c-6c4412e5b18d` (`[0:187]`) and `ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc` (`[579:729]`).
   - **Honest Boundary:** Reflects citations in the 31 July 2026 archive; does not make unverified claims about current live crawl status.

3. **Diagnostic 3: Brand Entity Confusion with 'Kaspr' / Similar Names**
   - **Observed Pattern:** 20 responses reference phonetically similar entities such as 'Kaspr' or 'Gaspar AI' (including G2/pricing disambiguation notes), splitting entity attribution.
   - **Supporting Citations:** Verified against `136b8240-008c-46ff-b744-592c4d859e98` (`[0:58]`) and `1d2dc007-0757-480d-a086-6b6e2e13c463` (`[0:191]`).
   - **Honest Boundary:** Proven name collision in prompt answers; distinguishes phonetic confusion from intentional competitor comparison.

---

## 4. Verification of Prioritised Remedies (P4.4)

Each prioritized remedy follows logically from the diagnostic evidence and includes all seven required fields:

1. **Remedy 1: Publish Verified Third-Party Case Studies with Before/After GEO Metrics**
   - **Problem:** Negative/cautionary characterization reached 6.0% on ChatGPT, citing lack of independent proof (Diagnostic 2).
   - **Supporting Evidence:** Responses `08f81acc-0824-4e3a-a5d5-58446e2a6a90`, `5492b420-7fa5-4de4-ab2c-6c4412e5b18d`, `847af3d3-88c3-4cad-ad9f-a1a4d6889052`.
   - **Recommended Action:** Produce and publish 3 detailed customer case studies on independent third-party platforms with verifiable before/after visibility metrics.
   - **Expected Benefit:** Displaces cautionary ScamAdviser citations with verifiable trust signals for retrieval engines.
   - **Effort:** Medium (Customer approvals + editorial packaging).
   - **Uncertainty:** Search index ingestion cycles vary over days to weeks.
   - **Measurable Validation:** Re-evaluate branded trust prompts after publication; target: 0 ScamAdviser citations.

2. **Remedy 2: Establish Official Profiles on Software Review Directories (G2, Capterra, ProductHunt)**
   - **Problem:** Kasparro appeared in 0/75 unbranded category discovery queries, while competitors were surfaced from review directories (Diagnostic 1).
   - **Supporting Evidence:** Responses `0f38b477-9f3c-44a8-9d10-0b6016db6150`, `11010066-8ed2-4741-856e-9259ae1a377b`.
   - **Recommended Action:** Claim and populate verified vendor profiles under AI Search Optimization and collect verified user reviews.
   - **Expected Benefit:** Strengthens category co-occurrence in buyer discovery queries.
   - **Effort:** Low (Profile creation and review collection).
   - **Uncertainty:** Directory verification requires minimum customer review thresholds.
   - **Measurable Validation:** Re-run unbranded discovery prompts; track change in unbranded inclusion rate.

3. **Remedy 3: Implement Organization Schema.org Markup & Brand Disambiguation from 'Kaspr'**
   - **Problem:** Entity overlap with 'Kaspr' appeared in 20 responses/citations, diluting product entity attribution (Diagnostic 3).
   - **Supporting Evidence:** Responses `08f81acc-0824-4e3a-a5d5-58446e2a6a90`, `136b8240-008c-46ff-b744-592c4d859e98`, `1d2dc007-0757-480d-a086-6b6e2e13c463`.
   - **Recommended Action:** Deploy JSON-LD Organization schema on kasparro.com with explicit `sameAs` links and publish an entity clarification page distinguishing Kasparro (AISO) from Kaspr (B2B contact data).
   - **Expected Benefit:** Clarifies entity resolution for knowledge graph crawlers.
   - **Effort:** Low (Technical schema markup deployment).
   - **Uncertainty:** Knowledge graph updates propagate over multiple crawl cycles.
   - **Measurable Validation:** Verify Rich Results validation passes; monitor disambiguation citations.

---

## 5. Clean Execution Mode Separation (P4.5)

The analysis cleanly segregates the three execution tiers to prevent misleading claims:

| Tier | Dataset / Scope | Execution Type | Metrics / Findings | File Outputs |
|---|---|---|---|---|
| **1. Historical Capture** | 150 archived responses (31 July 2026) | Static Dataset | Overall score: 33.04; Inclusion: 48.0%; Rec: 6.0%; Neg: 3.33% | `final_report.json`, `prompt_scores.json`, `report.html` |
| **2. Deterministic Replay** | 20 regression + 30 held-out cases | Rule-based (v1) | Regression: 100.0% agreement; Held-out: 63.3% agreement | `eval_results.json`, `eval_comparison_report.md`, `eval_held_out_results.json` |
| **3. Real-Model Provider** | 20 cases (1-pass) + 60 calls (3-run repeatability) | Live Gemini API (`gemini-3.5-flash-lite`) | Single pass: 73.7% agreement (+21.1% vs baseline), 95.0% coverage (1 HTTP 429 quota failure); Repeatability: 88.89% stability, 90.0% coverage (6 quota failures) | `eval_provider_results.json`, `eval_provider_report.md`, `repeatability_regression.json` |

- Real-model results are **never** presented as the score of the 150 historical responses.
- Replay results are **never** presented as real-model LLM accuracy.
- Quota throttles (HTTP 429) are recorded explicitly in execution coverage rather than hidden.

---

## 6. Test Suite and Verification Results (P4.7)

* **P4 Reconciliation Tests:** `pytest -v tests/test_p4_reconciliation.py` — **3 passed** (0.09s).
* **P3 Evidence Integrity Tests:** `pytest -v tests/test_p3_evidence_integrity.py` — **4 passed** (1.71s).
* **Full Automated Test Suite:** `pytest -q` — **122 passed**, 1 skipped, **0 failed** (11.02s).
* **Assignment Pack Integrity:** `python tools/check_pack.py` — **Passed** (50 prompts, 150 responses, 2439 citations validated).

