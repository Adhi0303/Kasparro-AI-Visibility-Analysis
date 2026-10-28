from typing import List, Dict, Any, Optional


def baseline_classify(text: str) -> Dict[str, bool]:
    """
    Simple naive keyword baseline for comparison against the proposed approach.
    """
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
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt and yp)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and yp)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and not yp)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt and not yp)

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if (precision is not None and recall is not None and (precision + recall) > 0)
        else None
    )

    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def grade_predictions(expected: List[Dict[str, bool]], actual: List[Dict[str, bool]]) -> Dict[str, Any]:
    labels = ["kasparro_mentioned", "kasparro_recommended", "kasparro_negative"]
    per_label_metrics = {}

    for lbl in labels:
        y_true = [e.get(lbl, False) for e in expected]
        y_pred = [a.get(lbl, False) for a in actual]
        per_label_metrics[lbl] = compute_label_metrics(y_true, y_pred)

    exact_matches = 0
    total = len(expected)
    for e, a in zip(expected, actual):
        if all(e.get(lbl, False) == a.get(lbl, False) for lbl in labels):
            exact_matches += 1

    agreement_rate = round(exact_matches / total, 4) if total > 0 else 0.0

    return {
        "total_cases": total,
        "exact_matches": exact_matches,
        "agreement_rate": agreement_rate,
        "per_label": per_label_metrics,
    }

