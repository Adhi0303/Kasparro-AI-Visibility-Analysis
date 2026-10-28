# Scoring Methodology & Metric Formulation

## 1. Visibility Scoring Formula (v1)

Brand visibility across AI answer engines cannot be captured by mere keyword counting. A brand cited only within a scam warning or buried as the 10th bullet point delivers drastically different value than an explicit top-rank recommendation.

To quantify this, the platform implements **Visibility Formula v1**:

$$\text{Visibility Score} = 100 \times \left( 0.30 \times I + 0.40 \times R + 0.20 \times P + 0.10 \times N \right)$$

Where:
* $I$ = **Inclusion Component** (Weight: 30%)
* $R$ = **Recommendation Component** (Weight: 40%)
* $P$ = **Prominence Component** (Weight: 20%)
* $N$ = **Non-Negative Component** (Weight: 10%)

---

## 2. Component Definitions & Scoring Rules

| Component | Weight | Allowed Values | Evaluation Logic |
| :--- | :---: | :---: | :--- |
| **Inclusion ($I$)** | 30% | `1.0` or `0.0` | **1.0** if Kasparro is explicitly mentioned in the generated answer text; **0.0** if completely absent. |
| **Recommendation ($R$)** | 40% | `1.0` or `0.0` | **1.0** if Kasparro is presented as an endorsed, recommended, or shortlisted solution; **0.0** if omitted or listed passively without endorsement. |
| **Prominence ($P$)** | 20% | $[0.0, 1.0]$ or `null` | Evaluated via **positional reciprocal decay** ($1 / \text{rank}$) when ordered in numbered lists. If unobservable, remains `null` (see below). |
| **Non-Negative ($N$)** | 10% | `1.0` or `0.0` | **1.0** if no adverse characterization is present; **0.0** if warning flags, ScamAdviser alerts, or negative qualifiers appear. |

### Component Weight Rationale

1. **Recommendation (40%)**: Carries the highest weight because conversational AI users rarely read full paragraphs; they act on the AI's top recommendations.
2. **Inclusion (30%)**: Being in the candidate set is the prerequisite for all discovery.
3. **Prominence (20%)**: Higher positioning in numbered lists correlates strongly with user click-through and selection.
4. **Non-Negative (10%)**: Even when recommended, negative flags (such as trust score warnings) erode buyer confidence.

---

## 3. Prominence Decay & Uncertainty Normalization

In unstructured natural language, list rank is not always observable (e.g. paragraph prose answers).

### Positional Reciprocal Decay
When a ordered list exists:
$$P = \frac{1}{\text{recommendation\_position}}$$

* Rank 1: $1 / 1 = 1.0$ (Score contribution: 20.0 pts)
* Rank 2: $1 / 2 = 0.5$ (Score contribution: 10.0 pts)
* Rank 3: $1 / 3 \approx 0.333$ (Score contribution: 6.67 pts)
* Rank 4: $1 / 4 = 0.25$ (Score contribution: 5.0 pts)

### Handling Unobservable Prominence (`null`)
When no explicit numbered list order exists, the system **never manufactures an artificial rank or fills with 0**. Doing so would unfairly penalize prose answers.

Instead, prominence is assigned `null`, and the available weights are normalized over the remaining 80% (0.80):

$$\text{Score}_{\text{normalized}} = 100 \times \frac{0.30 \times I + 0.40 \times R + 0.10 \times N}{0.30 + 0.40 + 0.10}$$

This guarantees a fair 0–100 scale without introducing artificial bias.

---

## 4. Denominator Integrity & Failure Isolation

In statistical aggregation, treating technical errors as "zero visibility" creates devastating false negatives. The platform strictly enforces denominator hygiene:

```
Total Ingested Responses: 150
  ├── Eligible for Scoring: 150
  │     ├── Successfully Scored: 150
  │     ├── Failed (timeouts/malformed): 0  --> score = null (excluded from denominator)
  │     └── Skipped: 0                      --> score = null (excluded from denominator)
```

$$\text{Mean Score} = \frac{\sum_{i \in \text{Successful}} \text{Score}_i}{N_{\text{Successful}}}$$

If a model times out or returns unparseable JSON:
* The response record is tagged `status = "failed"` with an explicit `failure_reason`.
* It is **omitted from the mean score denominator**.
* The failure count is surfaced prominently in all reports and API summaries.

---

## 5. Benchmark Metrics Summary (31 July 2026 Snapshot)

From the 150 archived responses across 50 prompts:

| Engine | Visibility Score (0–100) | Inclusion Rate | Recommendation Rate | Negative Rate | Responses |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Gemini** | **41.5** | 44.0% | 26.0% | 2.0% | 50 |
| **ChatGPT** | **36.5** | 50.0% | 14.0% | 12.0% | 50 |
| **Google AI Mode** | **34.8** | 50.0% | 8.0% | 4.0% | 50 |
| **Combined Overall** | **37.6** | **48.0%** | **16.0%** | **6.0%** | **150** |

