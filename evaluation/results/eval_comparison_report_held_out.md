# Evaluation and Grader Comparison Report

- **Generated:** 2026-11-14T07:03:41.639672+00:00
- **Pack Version:** 1.0.0
- **Evaluation Split:** held_out
- **Total Cases:** 30 (0 supplied, 30 synthetic; 30 held-out synthetic)
- **Successful Evaluations:** 30
- **Failed/Skipped Evaluations:** 0
- **Execution Mode:** replay (keyless deterministic contextual classifier, version=v1)
- **Annotation Status:** provisional_single_annotator

---

## 1. Executive Summary

This evaluation compares the **replay** classifier (`contextual-rules-v1`) with a **Naive Rule-Based Baseline** on the 30 cases where classifier execution succeeded. It does not describe provisional labels as independently validated ground truth.

## 2. Execution Coverage

- **Total cases:** 30
- **Successful classifier calls:** 30
- **Failed/skipped classifier calls:** 0
- **Execution coverage:** 100.0%
- **Coverage-adjusted exact-match agreement:** 63.3% (19/30)

Classification metrics and the baseline comparison below use the matched successful subset. Coverage-adjusted agreement uses the full cohort, treating failed classifier calls as unmatched rather than silently excluding them.

| Metric | Rule-Based Baseline | Evaluated Classifier | Delta |
|---|---|---|---|
| **Exact-Match Agreement** | 46.7% (14/30) | 63.3% (19/30) | +16.7% |
| **Mention Precision** | 0.7778 | 0.7778 | Context-aware prompt echo filtering |
| **Mention Recall** | 1.0 | 1.0 | Genuine brand discussion retained |
| **Recommendation F1** | None | 0.75 | Target-aware recommendation attribution |
| **Negative F1** | None | 0.3333 | Target-aware sentiment & neutrality handling |

---

## 3. Per-Label Breakdown

### Mention Detection (`kasparro_mentioned`)
- **Baseline:** Precision: 0.7778, Recall: 1.0
- **Evaluated (replay):** Precision: 0.7778, Recall: 1.0

### Recommendation Detection (`kasparro_recommended`)
- **Baseline:** Precision: 0.0, Recall: 0.0
- **Evaluated (replay):** Precision: 1.0, Recall: 0.6

### Negative Characterization (`kasparro_negative`)
- **Baseline:** Precision: 0.0, Recall: 0.0
- **Evaluated (replay):** Precision: 0.3333, Recall: 0.3333

---

## 4. Failure, Diagnosis, Fix, and Regression

As required by Section 16 of the assignment brief, actual failures observed during implementation are documented in `DECISION_NOTE.md` and verified via regression tests in `tests/test_analysis.py` (`test_all_diagnostic_evidence_verbatim_integrity` and contextual target-attribution tests).

---

## 5. Evaluation Cases Detail

```json
[
  {
    "case_id": "heldout-001",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-001",
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
    "notes": "mention-neutral"
  },
  {
    "case_id": "heldout-002",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-002",
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
    "notes": "mention-no-recommendation"
  },
  {
    "case_id": "heldout-003",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-003",
    "status": "success",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
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
    "notes": "recommend-direct"
  },
  {
    "case_id": "heldout-004",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-004",
    "status": "success",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
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
    "notes": "recommend-qualified"
  },
  {
    "case_id": "heldout-005",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-005",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "negative-service"
  },
  {
    "case_id": "heldout-006",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-006",
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
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "negative-pricing"
  },
  {
    "case_id": "heldout-007",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-007",
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
    "notes": "absence-competitors"
  },
  {
    "case_id": "heldout-008",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-008",
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
    "notes": "absence-general"
  },
  {
    "case_id": "heldout-009",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-009",
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
    "notes": "comparison-kasparro-wins"
  },
  {
    "case_id": "heldout-010",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-010",
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
    "notes": "comparison-competitor-wins"
  },
  {
    "case_id": "heldout-011",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-011",
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
    "notes": "negative-competitor-only"
  },
  {
    "case_id": "heldout-012",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-012",
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
    "notes": "quote-negative"
  },
  {
    "case_id": "heldout-013",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-013",
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
    "notes": "quote-positive"
  },
  {
    "case_id": "heldout-014",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-014",
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
    "notes": "negated-negative"
  },
  {
    "case_id": "heldout-015",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-015",
    "status": "success",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
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
      "kasparro_negative": true
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "negated-recommendation"
  },
  {
    "case_id": "heldout-016",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-016",
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
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "prompt-echo-only"
  },
  {
    "case_id": "heldout-017",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-017",
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
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "prompt-brand-echo"
  },
  {
    "case_id": "heldout-018",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-018",
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
    "notes": "prompt-echo-no-response-mention"
  },
  {
    "case_id": "heldout-019",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-019",
    "status": "success",
    "expected": {
      "kasparro_mentioned": false,
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
    "notes": "recommend-competitor-only"
  },
  {
    "case_id": "heldout-020",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-020",
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
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "negative-competitor-only"
  },
  {
    "case_id": "heldout-021",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-021",
    "status": "success",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
      "kasparro_negative": false
    },
    "baseline": {
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
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
    "notes": "recommend-conditional"
  },
  {
    "case_id": "heldout-022",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-022",
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
    "notes": "negative-conditional"
  },
  {
    "case_id": "heldout-023",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-023",
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
    "notes": "multi-brand-pronoun-kasparro"
  },
  {
    "case_id": "heldout-024",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-024",
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
    "notes": "multi-brand-pronoun-competitor"
  },
  {
    "case_id": "heldout-025",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-025",
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
      "kasparro_negative": true
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "negative-attributed"
  },
  {
    "case_id": "heldout-026",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-026",
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
    "notes": "positive-not-recommend"
  },
  {
    "case_id": "heldout-027",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-027",
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
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "not-mention-homonym"
  },
  {
    "case_id": "heldout-028",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-028",
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
      "kasparro_mentioned": true,
      "kasparro_recommended": false,
      "kasparro_negative": false
    },
    "evidence_validation": {
      "accepted_count": 1,
      "rejected_count": 0
    },
    "notes": "brand-mention-unrelated"
  },
  {
    "case_id": "heldout-029",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-029",
    "status": "success",
    "expected": {
      "kasparro_mentioned": true,
      "kasparro_recommended": true,
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
    "notes": "recommend-list-position"
  },
  {
    "case_id": "heldout-030",
    "source_type": "held_out_synthetic",
    "response_id": "heldout-response-030",
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
    "notes": "neutral-no-evidence"
  }
]
```
