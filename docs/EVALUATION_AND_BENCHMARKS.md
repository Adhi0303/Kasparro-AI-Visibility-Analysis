# Evaluation Framework, Diagnostics & Benchmark Results

## 1. Evaluation Methodology

To evaluate classifier reliability independently from application code tests, the platform features a gold-standard evaluation harness located in `evaluation/`.

### Labeled Evaluation Cases (`evaluation/cases.jsonl`)
The benchmark includes 10 gold-standard ground-truth cases:
* **8 Supplied Real Cases**: Spanning all three engines (Gemini, ChatGPT, AI Mode), branded queries, and unbranded queries.
* **2 Synthetic Adversarial Cases**:
  1. `eval-syn-001`: Prompt question repetition without AI brand endorsement.
  2. `eval-syn-002`: Competitor recommendation with a negative passing reference to Kasparro.

```mermaid
flowchart LR
    GOLD["Gold Cases (10 cases)\nevaluation/cases.jsonl"] --> GRADER["Grader Engine\nevaluation/grader.py"]
    BASELINE["Baseline Keyword Matcher\n(Simple substring matching)"] --> GRADER
    PROPOSED["Proposed Classifier\n(Context-aware heuristics & rules)"] --> GRADER
    GRADER --> RESULTS["Precision, Recall & F1\nBaseline: 50.0% vs Proposed: 70.0%"]
```

---

## 2. Benchmark Comparison: Baseline vs. Proposed

Running `python -m evaluation.run_eval` produces the comparative benchmark:

| Metric | Baseline (Keyword Regex) | Proposed Classifier | Improvement |
| :--- | :---: | :---: | :---: |
| **Overall Agreement** | **50.0%** | **70.0%** | **+20.0%** |
| Mention Precision | 62.5% | 87.5% | +25.0% |
| Mention Recall | 100.0% | 100.0% | 0.0% |
| Recommendation Precision | 40.0% | 66.7% | +26.7% |
| Recommendation Recall | 66.7% | 83.3% | +16.6% |
| Negative Detection Accuracy | 33.3% | 80.0% | +46.7% |

### Key Classifier Improvements Over Baseline:
1. **Disambiguation of Casual Mentions vs. Recommendations**: The baseline incorrectly scored any sentence containing "Kasparro" as a recommendation. The proposed classifier checks for recommendation verbs ("recommend", "shortlist", "stands out as", "ideal for").
2. **Adversarial Negative Sentiment Detection**: Successfully identifies negative reputation qualifiers (e.g. ScamAdviser citations) rather than classifying them as neutral mentions.

---

## 3. Real Findings & Diagnostics (Historical Snapshot)

From the 150 responses captured on 31 July 2026 across ChatGPT, Gemini, and Google AI Mode:

### Diagnostic 1: Complete Absence in Unbranded Category Searches
* **Finding**: Kasparro achieved **0 mentions out of 75 unbranded category responses** across all 3 engines ($0.0\%$ recall).
* **Observed Data**: In generic buyer queries (e.g. "what is the best software for measuring brand inclusion in AI search answers?"), competitors **Profound**, **Peec AI**, and **Otterly** were cited and recommended instead.
* **Verbatim Evidence (`0f38b477-9f3c-44a8-9d10-0b6016db6150`, Gemini)**:
  > *"Profound is a powerhouse in the AI visibility space. It tracks an extensive array of engines (10+ platforms including niche models like Grok and DeepSeek)."*
* **Strategic Implication**: Kasparro has an acute top-of-funnel discoverability void. Buyers searching for solutions without already knowing the brand name will never encounter Kasparro in AI engines.

---

### Diagnostic 2: ChatGPT Skepticism & Negative Trust Profiling
* **Finding**: ChatGPT exhibited a **12.0% negative characterization rate** (compared to 2.0% in Gemini and 4.0% in AI Mode).
* **Root Cause & Evidence**: ChatGPT repeatedly cited ScamAdviser and flagged the absence of independent third-party evidence.
* **Verbatim Evidence (`ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc`, ChatGPT)**:
  > *"However, I couldn't find independent evidence showing that Kasparro consistently delivers measurable improvements for B2B SaaS companies specifically. Most of the publicly available material is the company's own positioning rather than third-party case studies with before/after data. [www.scamadviser.com](https://www.scamadviser.com/check-website/kasparro.com?utm_source=chatgpt.com)"*
* **Impact**: Suppressed ChatGPT Visibility Score to 36.5 despite a 50% inclusion rate.

---

### Diagnostic 3: Phonetic Brand Confusion with "Kaspr"
* **Finding**: AI Mode and ChatGPT repeatedly confused **Kasparro** (an AI Visibility/GEO platform) with **Kaspr** (a LinkedIn B2B contact enrichment tool).
* **Verbatim Evidence (`08f81acc-0824-4e3a-a5d5-58446e2a6a90`, ChatGPT / Prompt 005)**:
  > *"**Kasparro** (often searched or spelled similarly to \*Kaspr\*, a well-known LinkedIn contact-data finder) is a legitimate, early-stage B2B SaaS startup operating in the emerging **AI Visibility and Brand Intelligence** space..."*
* **Impact**: Confuses buyer intent and dilutes positioning as an AI search analytics provider.

---

## 4. Prioritized Remedies Roadmap

| Priority | Action Item | Target Engine | Expected Impact | Implementation Effort | Validation Metric |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **R1** | **B2B Directory & Review Site Profiling**<br>Publish claimed profiles on G2, Capterra, ProductHunt, and Trustpilot. | All Engines | Eliminates 0% unbranded discovery void; seeds LLM retrieval indices. | **Low** (1–2 weeks) | Unbranded query recall rises from $0.0\%$ to $\ge 25.0\%$ in 60-day re-crawl. |
| **R2** | **Technical Domain Trust Remediation**<br>Verify WHOIS ownership, register EV SSL certificate, submit site to Web of Trust & ScamAdviser. | ChatGPT | Clears scam flag citations and elevates ChatGPT score from 36.5 to ~45+. | **Low** (3–5 days) | ChatGPT negative sentiment rate drops from $12.0\%$ to $< 2.0\%$. |
| **R3** | **Entity Disambiguation via Structured Data**<br>Implement JSON-LD `SoftwareApplication` schema explicitly differentiating Kasparro from Kaspr. | AI Mode & Gemini | Prevents feature hallucination and sales prospecting misclassification. | **Medium** (2 weeks) | B2B lead scraping misattributions fall from $14.0\%$ to $0.0\%$. |

