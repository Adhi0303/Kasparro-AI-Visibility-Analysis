from typing import List, Dict, Any


LABELS = ("kasparro_mentioned", "kasparro_recommended", "kasparro_negative")


def baseline_classify(text: str) -> Dict[str, bool]:
    """Simple naive keyword baseline for comparison against the proposed approach."""
    t = text.lower()
    mentioned = "kasparro" in t
    recommended = mentioned and ("recommend" in t or "top" in t) and ("not recommend" not in t)
    negative = mentioned and ("scam" in t or "bad" in t or "not recommend" in t)
    return {
        "kasparro_mentioned": mentioned,
        "kasparro_recommended": recommended,
        "kasparro_negative": negative,
    }


def compute_label_metrics(y_true: List[bool], y_pred: List[bool]) -> Dict[str, Any]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must contain the same number of labels")
    if any(type(value) is not bool for value in y_true + y_pred):
        raise TypeError("All ground-truth and predicted labels must be booleans")

    tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth and pred)
    fp = sum(1 for truth, pred in zip(y_true, y_pred) if not truth and pred)
    tn = sum(1 for truth, pred in zip(y_true, y_pred) if not truth and not pred)
    fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth and not pred)

    precision = round(tp / (tp + fp), 4) if tp + fp else None
    recall = round(tp / (tp + fn), 4) if tp + fn else None
    specificity = round(tn / (tn + fp), 4) if tn + fp else None
    accuracy = round((tp + tn) / len(y_true), 4) if y_true else None
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    balanced_accuracy = (
        round((recall + specificity) / 2, 4)
        if recall is not None and specificity is not None
        else None
    )

    return {
        "support": len(y_true),
        "positive_support": tp + fn,
        "negative_support": tn + fp,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "f1": f1,
    }


def grade_predictions(expected: List[Dict[str, bool]], actual: List[Dict[str, bool]]) -> Dict[str, Any]:
    if len(expected) != len(actual):
        raise ValueError("Expected and actual predictions must contain the same number of cases")

    per_label_metrics = {}
    for label in LABELS:
        y_true = [case.get(label, False) for case in expected]
        y_pred = [case.get(label, False) for case in actual]
        per_label_metrics[label] = compute_label_metrics(y_true, y_pred)

    exact_matches = sum(
        1 for expected_case, actual_case in zip(expected, actual)
        if all(expected_case.get(label, False) == actual_case.get(label, False) for label in LABELS)
    )
    total = len(expected)
    return {
        "total_cases": total,
        "exact_matches": exact_matches,
        "agreement_rate": round(exact_matches / total, 4) if total else 0.0,
        "per_label": per_label_metrics,
    }
