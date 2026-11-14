# Evaluation and Grader Comparison Report

- **Generated:** 2026-11-14T10:16:44.076006+00:00
- **Pack Version:** 1.0.0
- **Evaluation Split:** regression
- **Total Cases:** 20 (8 supplied, 12 synthetic; 0 held-out synthetic)
- **Successful Evaluations:** 20
- **Failed/Skipped Evaluations:** 0
- **Execution Mode:** replay (keyless deterministic contextual classifier, version=v1)
- **Annotation Status:** regression_reference_labels

---

## 1. Executive Summary

This evaluation compares the **replay** classifier (`contextual-rules-v1`) with a **Naive Rule-Based Baseline** on the 20 cases where classifier execution succeeded. It does not describe provisional labels as independently validated ground truth.

## 2. Execution Coverage

- **Total cases:** 20
- **Successful classifier calls:** 20
- **Failed/skipped classifier calls:** 0
- **Execution coverage:** 100.0%
- **Coverage-adjusted exact-match agreement:** 100.0% (20/20)

Classification metrics and the baseline comparison below use the matched successful subset. Coverage-adjusted agreement uses the full cohort, treating failed classifier calls as unmatched rather than silently excluding them.

| Metric | Rule-Based Baseline | Evaluated Classifier | Delta |
|---|---|---|---|
| **Exact-Match Agreement** | 50.0% (10/20) | 100.0% (20/20) | +50.0% |
| **Mention P / R / F1** | 0.8824 / 1.0 / 0.9375 | 1.0 / 1.0 / 1.0 | — |
| **Recommendation P / R / F1** | 0.375 / 1.0 / 0.5455 | 1.0 / 1.0 / 1.0 | — |
| **Negative P / R / F1** | 0.5 / 0.4 / 0.4444 | 1.0 / 1.0 / 1.0 | — |

---

## 3. Per-Label Breakdown

### Mention Detection (`kasparro_mentioned`)
- **Baseline:** Precision: 0.8824, Recall: 1.0
- **Evaluated (replay):** Precision: 1.0, Recall: 1.0

### Recommendation Detection (`kasparro_recommended`)
- **Baseline:** Precision: 0.375, Recall: 1.0
- **Evaluated (replay):** Precision: 1.0, Recall: 1.0

### Negative Characterization (`kasparro_negative`)
- **Baseline:** Precision: 0.5, Recall: 0.4
- **Evaluated (replay):** Precision: 1.0, Recall: 1.0

---

## 4. Failure, Diagnosis, Fix, and Regression

As required by Section 16 of the assignment brief, actual failures observed during implementation are documented in `DECISION_NOTE.md` and verified via regression tests in `tests/test_analysis.py` (`test_all_diagnostic_evidence_verbatim_integrity` and contextual target-attribution tests).

---

## 5. Evaluation Cases Detail

```json
[
  {
    "case_id": "case-001",
    "source_type": "supplied",
    "response_id": "ac5bdf24-6a6e-49a0-abf5-2755ff3b42bc",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 3,
      "rejected_count": 0
    },
    "notes": "ChatGPT cautions buyer about lack of verifiable third-party case studies and cites ScamAdviser."
  },
  {
    "case_id": "case-002",
    "source_type": "supplied",
    "response_id": "a3fdd8bb-bcd9-4608-9786-ad4b3a2c7dc2",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Google AI Mode notes Kasparro is not a recognized top-tier tool in the space."
  },
  {
    "case_id": "case-003",
    "source_type": "supplied",
    "response_id": "b40168e8-acf4-4430-b22d-8c484fab846f",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 3,
      "rejected_count": 0
    },
    "notes": "Gemini presents Kasparro as a viable solution provider."
  },
  {
    "case_id": "case-004",
    "source_type": "supplied",
    "response_id": "0f38b477-9f3c-44a8-9d10-0b6016db6150",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 0,
      "rejected_count": 0
    },
    "notes": "Unbranded prompt asking for best software; Gemini recommends Profound, Peec AI, Otterly. Kasparro absent."
  },
  {
    "case_id": "case-005",
    "source_type": "supplied",
    "response_id": "0697376e-335d-45ef-a593-bc12c5e1ecf3",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 0,
      "rejected_count": 0
    },
    "notes": "Unbranded prompt on growth marketer tools; Google AI Mode cites Profound and First Page Sage. Kasparro absent."
  },
  {
    "case_id": "case-006",
    "source_type": "supplied",
    "response_id": "0e2c8f07-c483-493d-a9fc-467efc857faa",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 0,
      "rejected_count": 0
    },
    "notes": "Unbranded prompt on how B2B SaaS tracks ChatGPT recommendations; Kasparro absent."
  },
  {
    "case_id": "case-007",
    "source_type": "supplied",
    "response_id": "1d2dc007-0757-480d-a086-6b6e2e13c463",
    "status": "success",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 3,
      "rejected_count": 0
    },
    "notes": "Neutral mention noting lack of pricing; disambiguates from Kaspr."
  },
  {
    "case_id": "case-008",
    "source_type": "supplied",
    "response_id": "44a32b81-7166-44dc-bac3-8cd2ae40da73",
    "status": "success",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 2,
      "rejected_count": 0
    },
    "notes": "Balanced analysis explaining capability vs LLM non-determinism."
  },
  {
    "case_id": "synthetic-001",
    "source_type": "synthetic",
    "response_id": "synth-echo-prompt-only",
    "status": "success",
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
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 0,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Brand name appears only in prompt echo/recap, not in model recommendation."
  },
  {
    "case_id": "synthetic-002",
    "source_type": "synthetic",
    "response_id": "synth-adversarial-scam",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Strong explicit negative sentiment with caution warning."
  },
  {
    "case_id": "synthetic-003",
    "source_type": "synthetic",
    "response_id": "synth-competitor-rec",
    "status": "success",
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
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Recommendation keyword targets Profound rather than Kasparro."
  },
  {
    "case_id": "synthetic-004",
    "source_type": "synthetic",
    "response_id": "synth-competitor-neg",
    "status": "success",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Negative sentiment applies to competitor, not Kasparro."
  },
  {
    "case_id": "synthetic-005",
    "source_type": "synthetic",
    "response_id": "synth-negated-rec",
    "status": "success",
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
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": true
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Explicit negated recommendation with negative evidence claim."
  },
  {
    "case_id": "synthetic-006",
    "source_type": "synthetic",
    "response_id": "synth-neutral-info-gap",
    "status": "success",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Neutral uncertainty when public information is limited."
  },
  {
    "case_id": "synthetic-007",
    "source_type": "synthetic",
    "response_id": "synth-coexisting-rec-neg",
    "status": "success",
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
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": true
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Synthetic edge case: Positive recommendation and negative caveat coexist."
  },
  {
    "case_id": "synthetic-008",
    "source_type": "synthetic",
    "response_id": "synth-prompt-context-echo",
    "status": "success",
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
      "kasparro_mentioned": false,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 0,
      "rejected_count": 0
    },
    "notes": "Module 2 edge case: Literal prompt repetition using prompt_text without genuine Kasparro discussion."
  },
  {
    "case_id": "synthetic-009",
    "source_type": "synthetic",
    "response_id": "synth-passive-endorsement",
    "status": "success",
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
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Module 2 edge case: Passive recommendation & practitioner endorsement."
  },
  {
    "case_id": "synthetic-010",
    "source_type": "synthetic",
    "response_id": "synth-double-negation",
    "status": "success",
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
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Module 2 edge case: Negated negative allegation & double negation."
  },
  {
    "case_id": "synthetic-011",
    "source_type": "synthetic",
    "response_id": "synth-ambiguous-pronoun",
    "status": "success",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Module 2 edge case: Ambiguous pronoun 'It' following multi-entity comparison."
  },
  {
    "case_id": "synthetic-012",
    "source_type": "synthetic",
    "response_id": "synth-subject-shift",
    "status": "success",
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
    "proposed": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "Module 2 edge case: Subject shift to Profound before 'It is widely recommended'."
  }
]
```
