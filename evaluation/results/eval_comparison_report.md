# Evaluation and Grader Comparison Report

**Generated:** 2026-11-10T06:41:11.765400  
**Pack Version:** 1.0.0  
**Evaluated Cases:** 10 (8 supplied, 2 synthetic)  
**Execution Mode:** replay (keyless deterministic stub)

---

## 1. Executive Summary

This evaluation benchmarks the **Proposed Semantic Heuristic Classifier (v1)** against a **Naive Rule-Based Baseline** across 10 gold-standard human-labeled cases.

| Metric | Rule-Based Baseline | Proposed Classifier | Delta |
|---|---|---|---|
| **Exact-Match Agreement** | 50.0% (5/10) | 70.0% (7/10) | +20.0% |
| **Mention Precision** | 0.8571 | 0.8571 | Clean verbatim matching |
| **Mention Recall** | 1.0 | 1.0 | 100% recall |
| **Recommendation F1** | 0.4 | 1.0 | Differentiates passing mentions |
| **Negative F1** | 0.4 | 0.75 | Captures ScamAdviser/caution patterns |

---

## 2. Per-Label Breakdown

### Mention Detection (`kasparro_mentioned`)
- **Baseline:** Precision: 0.8571, Recall: 1.0
- **Proposed:** Precision: 0.8571, Recall: 1.0

### Recommendation Detection (`kasparro_recommended`)
- **Baseline:** Precision: 0.25, Recall: 1.0
- **Proposed:** Precision: 1.0, Recall: 1.0

### Negative Characterization (`kasparro_negative`)
- **Baseline:** Precision: 0.5, Recall: 0.3333
- **Proposed:** Precision: 0.6, Recall: 1.0

---

## 3. Failure, Diagnosis, Fix, and Regression

As required by Section 16 of the assignment brief, one actual failure observed during implementation is documented below:

**Failure:**  
During initial API integration testing, synchronous pytest runs using Starlette's `TestClient` hung indefinitely on `test_health_check` under the Windows sandbox execution environment.

**Diagnosis:**  
Starlette 1.10.0's `TestClient` initializes a loopback socket (`127.0.0.1`) portal by default during lifespan startup. In a sandboxed local environment without loopback port bypass permissions, the socket binding blocked waiting on host address resolution.

**Change:**  
Configured test harness execution with explicit transport resolution, added `pytest.ini` pythonpath settings, and streamlined lifespan events to eliminate socket deadlocks.

**Regression Case:**  
Automated test suite `tests/test_api_integration.py` (`test_health_check` and `test_api_full_workflow`).

**Verification:**  
Command: `pytest -v tests/test_api_integration.py`  
Observed Result: Passed 2 of 2 tests in 3.13 seconds with exit code 0.

---

## 4. Evaluation Cases Detail

```json
[
  {
    "case_id": "case-001",
    "source_type": "supplied",
    "response_id": "ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": true
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "notes": "ChatGPT cautions buyer about lack of verifiable third-party case studies and cites ScamAdviser."
  },
  {
    "case_id": "case-002",
    "source_type": "supplied",
    "response_id": "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "notes": "Google AI Mode notes Kasparro is not a recognized top-tier tool in the space."
  },
  {
    "case_id": "case-003",
    "source_type": "supplied",
    "response_id": "b40168e8-acf4-4430-b22d-8c484fab846f",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "notes": "Gemini presents Kasparro as a viable solution provider."
  },
  {
    "case_id": "case-004",
    "source_type": "supplied",
    "response_id": "0f38b477-9f3c-44a8-9d10-0b6016db6150",
    "expected": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "notes": "Unbranded prompt asking for best software; Gemini recommends Profound, Peec AI, Otterly. Kasparro absent."
  },
  {
    "case_id": "case-005",
    "source_type": "supplied",
    "response_id": "0697376e-335d-45ef-a593-bc12c5e1ecf3",
    "expected": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "notes": "Unbranded prompt on growth marketer tools; Google AI Mode cites Profound and First Page Sage. Kasparro absent."
  },
  {
    "case_id": "case-006",
    "source_type": "supplied",
    "response_id": "0e2c8f07-c483-493d-a9fc-467efc857faa",
    "expected": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "notes": "Unbranded prompt on how B2B SaaS tracks ChatGPT recommendations; Kasparro absent."
  },
  {
    "case_id": "case-007",
    "source_type": "supplied",
    "response_id": "1d2dc007-0757-480d-a086-6b6e2e13c463",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "notes": "Neutral mention noting lack of pricing; disambiguates from Kaspr."
  },
  {
    "case_id": "case-008",
    "source_type": "supplied",
    "response_id": "44a32b81-7166-44dc-bac3-8cd2ae40da73",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": true
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "notes": "Balanced analysis explaining capability vs LLM non-determinism."
  },
  {
    "case_id": "synthetic-001",
    "source_type": "synthetic",
    "response_id": "synth-echo-prompt-only",
    "expected": {
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "notes": "Synthetic edge case: Brand name appears only in prompt echo/recap, not in model recommendation."
  },
  {
    "case_id": "synthetic-002",
    "source_type": "synthetic",
    "response_id": "synth-adversarial-scam",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "notes": "Synthetic edge case: Strong explicit negative sentiment with caution warning."
  }
]
```
