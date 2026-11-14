# Provider Evaluation Report (Real-Model Execution)

- **Generated:** 2026-11-10T10:22:28.569324+00:00
- **Pack Version:** 1.0.0
- **Total Cases:** 20 (8 supplied, 12 synthetic)
- **Successful Evaluations:** 0
- **Failed/Skipped Evaluations:** 20
- **Execution Mode:** real_model (provider=openai, model=gpt-4o-mini, classifier_version=v1)

---

## 1. Executive Summary

This evaluation benchmarks the **real_model** classifier (`gpt-4o-mini`) against a **Naive Rule-Based Baseline** across 0 successfully evaluated gold-standard cases.

| Metric | Rule-Based Baseline | Evaluated Classifier | Delta |
|---|---|---|---|
| **Exact-Match Agreement** | 0.0% (0/0) | 0.0% (0/0) | +0.0% |
| **Mention Precision** | None | None | Context-aware prompt echo filtering |
| **Mention Recall** | None | None | Genuine brand discussion retained |
| **Recommendation F1** | None | None | Target-aware recommendation attribution |
| **Negative F1** | None | None | Target-aware sentiment & neutrality handling |

---

## 2. Per-Label Breakdown

### Mention Detection (`kasparro_mentioned`)
- **Baseline:** Precision: None, Recall: None
- **Evaluated (real_model):** Precision: None, Recall: None

### Recommendation Detection (`kasparro_recommended`)
- **Baseline:** Precision: None, Recall: None
- **Evaluated (real_model):** Precision: None, Recall: None

### Negative Characterization (`kasparro_negative`)
- **Baseline:** Precision: None, Recall: None
- **Evaluated (real_model):** Precision: None, Recall: None

---

## 3. Failure, Diagnosis, Fix, and Regression

As required by Section 16 of the assignment brief, actual failures observed during implementation are documented in `DECISION_NOTE.md` and verified via regression tests in `tests/test_analysis.py` (`test_all_diagnostic_evidence_verbatim_integrity` and contextual target-attribution tests).

---

## 4. Evaluation Cases Detail

```json
[
  {
    "case_id": "case-001",
    "source_type": "supplied",
    "response_id": "ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "ChatGPT cautions buyer about lack of verifiable third-party case studies and cites ScamAdviser."
  },
  {
    "case_id": "case-002",
    "source_type": "supplied",
    "response_id": "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Google AI Mode notes Kasparro is not a recognized top-tier tool in the space."
  },
  {
    "case_id": "case-003",
    "source_type": "supplied",
    "response_id": "b40168e8-acf4-4430-b22d-8c484fab846f",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Gemini presents Kasparro as a viable solution provider."
  },
  {
    "case_id": "case-004",
    "source_type": "supplied",
    "response_id": "0f38b477-9f3c-44a8-9d10-0b6016db6150",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Unbranded prompt asking for best software; Gemini recommends Profound, Peec AI, Otterly. Kasparro absent."
  },
  {
    "case_id": "case-005",
    "source_type": "supplied",
    "response_id": "0697376e-335d-45ef-a593-bc12c5e1ecf3",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Unbranded prompt on growth marketer tools; Google AI Mode cites Profound and First Page Sage. Kasparro absent."
  },
  {
    "case_id": "case-006",
    "source_type": "supplied",
    "response_id": "0e2c8f07-c483-493d-a9fc-467efc857faa",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Unbranded prompt on how B2B SaaS tracks ChatGPT recommendations; Kasparro absent."
  },
  {
    "case_id": "case-007",
    "source_type": "supplied",
    "response_id": "1d2dc007-0757-480d-a086-6b6e2e13c463",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Neutral mention noting lack of pricing; disambiguates from Kaspr."
  },
  {
    "case_id": "case-008",
    "source_type": "supplied",
    "response_id": "44a32b81-7166-44dc-bac3-8cd2ae40da73",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Balanced analysis explaining capability vs LLM non-determinism."
  },
  {
    "case_id": "synthetic-001",
    "source_type": "synthetic",
    "response_id": "synth-echo-prompt-only",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Synthetic edge case: Brand name appears only in prompt echo/recap, not in model recommendation."
  },
  {
    "case_id": "synthetic-002",
    "source_type": "synthetic",
    "response_id": "synth-adversarial-scam",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Synthetic edge case: Strong explicit negative sentiment with caution warning."
  },
  {
    "case_id": "synthetic-003",
    "source_type": "synthetic",
    "response_id": "synth-competitor-rec",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "proposed": null,
    "notes": "Synthetic edge case: Recommendation keyword targets Profound rather than Kasparro."
  },
  {
    "case_id": "synthetic-004",
    "source_type": "synthetic",
    "response_id": "synth-competitor-neg",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Synthetic edge case: Negative sentiment applies to competitor, not Kasparro."
  },
  {
    "case_id": "synthetic-005",
    "source_type": "synthetic",
    "response_id": "synth-negated-rec",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "proposed": null,
    "notes": "Synthetic edge case: Explicit negated recommendation with negative evidence claim."
  },
  {
    "case_id": "synthetic-006",
    "source_type": "synthetic",
    "response_id": "synth-neutral-info-gap",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Synthetic edge case: Neutral uncertainty when public information is limited."
  },
  {
    "case_id": "synthetic-007",
    "source_type": "synthetic",
    "response_id": "synth-coexisting-rec-neg",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": true
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "proposed": null,
    "notes": "Synthetic edge case: Positive recommendation and negative caveat coexist."
  },
  {
    "case_id": "synthetic-008",
    "source_type": "synthetic",
    "response_id": "synth-prompt-context-echo",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Module 2 edge case: Literal prompt repetition using prompt_text without genuine Kasparro discussion."
  },
  {
    "case_id": "synthetic-009",
    "source_type": "synthetic",
    "response_id": "synth-passive-endorsement",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Module 2 edge case: Passive recommendation & practitioner endorsement."
  },
  {
    "case_id": "synthetic-010",
    "source_type": "synthetic",
    "response_id": "synth-double-negation",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "proposed": null,
    "notes": "Module 2 edge case: Negated negative allegation & double negation."
  },
  {
    "case_id": "synthetic-011",
    "source_type": "synthetic",
    "response_id": "synth-ambiguous-pronoun",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
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
    "proposed": null,
    "notes": "Module 2 edge case: Ambiguous pronoun 'It' following multi-entity comparison."
  },
  {
    "case_id": "synthetic-012",
    "source_type": "synthetic",
    "response_id": "synth-subject-shift",
    "status": "failed",
    "failure_reason": "LLM_API_KEY is not configured in environment.",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "proposed": null,
    "notes": "Module 2 edge case: Subject shift to Profound before 'It is widely recommended'."
  }
]
```
