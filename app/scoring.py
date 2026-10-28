from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class ScoreComponents(BaseModel):
    inclusion: float
    recommendation: float
    prominence: Optional[float] = None
    non_negative: float
    scoring_version: str = "v1"


class ScoreResult(BaseModel):
    score: Optional[float] = None
    status: str  # calculated, unavailable
    components: Optional[ScoreComponents] = None
    reason: Optional[str] = None


def calculate_visibility_score(
    status: str,
    kasparro_mentioned: bool,
    kasparro_recommended: bool,
    kasparro_negative: bool,
    recommendation_position: Optional[int] = None,
    scoring_version: str = "v1",
) -> ScoreResult:
    """
    Computes deterministic visibility score (0-100) based on v1 scoring weights:
    - Inclusion: 30% (1.0 if mentioned, 0.0 if absent)
    - Recommendation: 40% (1.0 if recommended, 0.0 if not)
    - Prominence: 20% (1.0 / rank if observable; normalized if unobservable)
    - Non-negative: 10% (1.0 if not negative, 0.0 if negative)
    """
    if status != "success":
        return ScoreResult(
            score=None,
            status="unavailable",
            reason=f"Classification status is '{status}', cannot calculate score."
        )

    # 1. Inclusion component
    inclusion = 1.0 if kasparro_mentioned else 0.0

    # 2. Recommendation component
    recommendation = 1.0 if kasparro_recommended else 0.0

    # 3. Non-negative component
    non_negative = 0.0 if kasparro_negative else 1.0

    # 4. Prominence component
    prominence: Optional[float] = None
    if recommendation_position is not None and recommendation_position > 0:
        prominence = round(min(1.0, 1.0 / recommendation_position), 4)

    # Calculate final score
    if prominence is not None:
        raw_score = (
            0.30 * inclusion +
            0.40 * recommendation +
            0.20 * prominence +
            0.10 * non_negative
        )
        final_score = round(100.0 * raw_score, 2)
    else:
        # If prominence is unobservable, normalize available components (sum of weights = 0.80)
        available_weights = 0.30 + 0.40 + 0.10
        raw_score = (
            0.30 * inclusion +
            0.40 * recommendation +
            0.10 * non_negative
        ) / available_weights
        final_score = round(100.0 * raw_score, 2)

    components = ScoreComponents(
        inclusion=inclusion,
        recommendation=recommendation,
        prominence=prominence,
        non_negative=non_negative,
        scoring_version=scoring_version,
    )

    return ScoreResult(
        score=final_score,
        status="calculated",
        components=components
    )


def compute_aggregate_scores(scored_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes mean score, eligibility counts, and distributions for aggregates.
    """
    total_eligible = len(scored_items)
    successful = [item for item in scored_items if item.get("status") == "success"]
    failed = [item for item in scored_items if item.get("status") == "failed"]
    skipped = [item for item in scored_items if item.get("status") == "skipped"]

    scored_values = [
        item["score"] for item in successful
        if item.get("score") is not None
    ]

    mean_score = round(sum(scored_values) / len(scored_values), 2) if scored_values else None

    # Distributions
    total_successful = len(successful)
    mentioned_count = sum(1 for item in successful if item.get("kasparro_mentioned", False))
    recommended_count = sum(1 for item in successful if item.get("kasparro_recommended", False))
    negative_count = sum(1 for item in successful if item.get("kasparro_negative", False))

    return {
        "total_eligible": total_eligible,
        "total_successful": total_successful,
        "total_failed": len(failed),
        "total_skipped": len(skipped),
        "mean_score": mean_score,
        "distribution": {
            "inclusion_rate": round(mentioned_count / total_successful, 4) if total_successful else 0.0,
            "recommendation_rate": round(recommended_count / total_successful, 4) if total_successful else 0.0,
            "negative_rate": round(negative_count / total_successful, 4) if total_successful else 0.0,
        }
    }

