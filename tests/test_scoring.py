import pytest
from app.scoring import calculate_visibility_score, compute_aggregate_scores


def test_perfect_visibility_score():
    # Mentioned (1.0), Recommended (1.0), Prominence rank 1 (1.0), Not negative (1.0)
    # score = 100 * (0.30*1 + 0.40*1 + 0.20*1 + 0.10*1) = 100.0
    res = calculate_visibility_score(
        status="success",
        kasparro_mentioned=True,
        kasparro_recommended=True,
        kasparro_negative=False,
        recommendation_position=1
    )
    assert res.status == "calculated"
    assert res.score == 100.0
    assert res.components.inclusion == 1.0
    assert res.components.recommendation == 1.0
    assert res.components.prominence == 1.0
    assert res.components.non_negative == 1.0


def test_absent_visibility_score():
    # Absent (0.0), Not recommended (0.0), Prominence None, Not negative (1.0)
    # Available weights sum = 0.80
    # score = 100 * (0.10 * 1.0 / 0.80) = 12.50
    res = calculate_visibility_score(
        status="success",
        kasparro_mentioned=False,
        kasparro_recommended=False,
        kasparro_negative=False,
        recommendation_position=None
    )
    assert res.status == "calculated"
    assert res.score == 12.50


def test_mentioned_negative_visibility_score():
    # Mentioned (1.0), Not recommended (0.0), Negative (0.0), Prominence None
    # score = 100 * (0.30 * 1.0 / 0.80) = 37.50
    res = calculate_visibility_score(
        status="success",
        kasparro_mentioned=True,
        kasparro_recommended=False,
        kasparro_negative=True,
        recommendation_position=None
    )
    assert res.status == "calculated"
    assert res.score == 37.50


def test_failed_status_excludes_score():
    # Failed response should return unavailable, NEVER score 0.0
    res = calculate_visibility_score(
        status="failed",
        kasparro_mentioned=False,
        kasparro_recommended=False,
        kasparro_negative=False,
    )
    assert res.status == "unavailable"
    assert res.score is None


def test_aggregate_scores():
    items = [
        {"status": "success", "score": 100.0, "kasparro_mentioned": True, "kasparro_recommended": True, "kasparro_negative": False},
        {"status": "success", "score": 50.0, "kasparro_mentioned": True, "kasparro_recommended": False, "kasparro_negative": True},
        {"status": "failed", "score": None, "kasparro_mentioned": False, "kasparro_recommended": False, "kasparro_negative": False},
    ]
    agg = compute_aggregate_scores(items)
    assert agg["total_eligible"] == 3
    assert agg["total_successful"] == 2
    assert agg["total_failed"] == 1
    assert agg["total_skipped"] == 0
    assert agg["mean_score"] == 75.0
    assert agg["distribution"]["inclusion_rate"] == 1.0
    assert agg["distribution"]["recommendation_rate"] == 0.5
    assert agg["distribution"]["negative_rate"] == 0.5

