import json
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Response as DBResponse, ResponseResult
from app.llm import get_classifier
from app.config import get_settings
from app.evidence import validate_evidence
from app.scoring import calculate_visibility_score, compute_aggregate_scores
from app.categories import categorize_prompt, CATEGORIES
from app.schemas import AnalysisStatusResponse


def execute_analysis(
    db: Session,
    dataset_id: str,
    execution_mode: str = "replay",
    classifier_version: str = "v1",
    scoring_version: str = "v1",
) -> AnalysisRun:
    settings = get_settings()

    analysis = AnalysisRun(
        dataset_id=dataset_id,
        execution_mode=execution_mode,
        classifier_version=classifier_version,
        scoring_version=scoring_version,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(analysis)
    db.flush()

    classifier = get_classifier(
        settings=settings,
        execution_mode=execution_mode,
        classifier_version=classifier_version,
    )

    responses = db.query(DBResponse).filter(DBResponse.dataset_id == dataset_id).all()

    # Load prompt text map for categorization
    prompts_map = {}
    for r in responses:
        try:
            payload = json.loads(r.raw_payload)
            prompts_map[r.prompt_id] = payload.get("prompt_text") or payload.get("text") or ""
        except Exception:
            prompts_map[r.prompt_id] = ""

    scored_records: List[Dict[str, Any]] = []

    for resp in responses:
        payload = json.loads(resp.raw_payload)
        answer_text = payload.get("answer_text", "")

        # Run classification
        classif = classifier.classify(
            response_id=resp.source_response_id,
            engine=resp.engine,
            answer_text=answer_text,
        )

        # Validate evidence excerpts verbatim
        validated_evidence = []
        for ev in classif.evidence:
            is_valid, _ = validate_evidence(ev.excerpt, answer_text)
            if is_valid:
                validated_evidence.append(ev.model_dump())

        # Calculate score
        score_res = calculate_visibility_score(
            status=classif.status,
            kasparro_mentioned=classif.kasparro_mentioned,
            kasparro_recommended=classif.kasparro_recommended,
            kasparro_negative=classif.kasparro_negative,
            recommendation_position=classif.recommendation_position,
            scoring_version=scoring_version,
        )

        db_result = ResponseResult(
            analysis_id=analysis.id,
            response_id=resp.id,
            status=classif.status,
            labels_json=json.dumps(classif.model_dump()),
            components_json=json.dumps(score_res.components.model_dump() if score_res.components else None),
            score=score_res.score,
            evidence_json=json.dumps(validated_evidence),
            failure_reason=classif.failure_reason,
        )
        db.add(db_result)

        scored_records.append({
            "response_id": resp.source_response_id,
            "engine": resp.engine,
            "prompt_id": resp.prompt_id,
            "status": classif.status,
            "score": score_res.score,
            "kasparro_mentioned": classif.kasparro_mentioned,
            "kasparro_recommended": classif.kasparro_recommended,
            "kasparro_negative": classif.kasparro_negative,
            "competitors": classif.competitors,
            "evidence": validated_evidence,
        })

    # Compute aggregates
    overall_agg = compute_aggregate_scores(scored_records)

    # Engine aggregates
    engine_aggregates = {}
    for eng in ("aimode", "chatgpt", "gemini"):
        eng_items = [item for item in scored_records if item["engine"] == eng]
        engine_aggregates[eng] = compute_aggregate_scores(eng_items)

    # Category aggregates
    category_aggregates = {}
    for cat in CATEGORIES:
        cat_items = [
            item for item in scored_records
            if categorize_prompt(prompts_map.get(item["prompt_id"], "")) == cat
        ]
        category_aggregates[cat] = compute_aggregate_scores(cat_items)

    summary_config = {
        "overall": overall_agg,
        "engine_aggregates": engine_aggregates,
        "category_aggregates": category_aggregates,
    }

    analysis.status = "completed"
    analysis.completed_at = datetime.utcnow()
    analysis.configuration_json = json.dumps(summary_config)

    db.commit()
    return analysis


def get_analysis_status(db: Session, analysis_id: str) -> AnalysisStatusResponse:
    analysis = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_id).first()
    if not analysis:
        raise ValueError(f"Analysis '{analysis_id}' not found")

    config = json.loads(analysis.configuration_json) if analysis.configuration_json else {}
    overall = config.get("overall", {})

    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        dataset_id=analysis.dataset_id,
        status=analysis.status,
        execution_mode=analysis.execution_mode,
        classifier_version=analysis.classifier_version,
        scoring_version=analysis.scoring_version,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        total_eligible=overall.get("total_eligible", 0),
        total_successful=overall.get("total_successful", 0),
        total_failed=overall.get("total_failed", 0),
        total_skipped=overall.get("total_skipped", 0),
        mean_score=overall.get("mean_score"),
        engine_aggregates=config.get("engine_aggregates", {}),
        category_aggregates=config.get("category_aggregates", {}),
    )

