"""
EvaluationService — runs the experiment motor and persists ExperimentEvaluation.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import structlog
from packages.experiment_engine.evaluator import evaluate_experiment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models.audit import AuditLog
from app.models.evaluation import ExperimentEvaluation
from app.models.experiment import Experiment
from app.models.variant_metric import VariantPerformanceSnapshot

logger = structlog.get_logger()


class EvaluationService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def evaluate(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
        notes: str | None = None,
    ) -> ExperimentEvaluation:
        # Load experiment + variants
        result = await db.execute(
            select(Experiment)
            .where(Experiment.id == experiment_id, Experiment.organization_id == org_id)
            .options(selectinload(Experiment.variants))
        )
        exp = result.scalar_one_or_none()
        if not exp:
            raise ValueError("Experiment not found.")

        if exp.status not in ("running", "evaluating", "completed"):
            raise ValueError(f"Cannot evaluate experiment in status '{exp.status}'.")

        # Load matured snapshots for each variant
        variant_ids = [v.id for v in exp.variants]
        snap_result = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.experiment_id == experiment_id,
                VariantPerformanceSnapshot.organization_id == org_id,
                VariantPerformanceSnapshot.variant_id.in_(variant_ids),
            )
        )
        all_snaps = snap_result.scalars().all()

        snaps_by_variant: dict[str, list[VariantPerformanceSnapshot]] = {}
        for snap in all_snaps:
            vid = str(snap.variant_id)
            snaps_by_variant.setdefault(vid, []).append(snap)

        variants_dicts = [
            {"id": str(v.id), "name": v.name, "is_control": v.is_control}
            for v in exp.variants
        ]

        min_criteria = _build_criteria(exp, self._settings)
        primary_metric = exp.primary_metric or "ctr"

        # Run pure evaluator
        eval_result = evaluate_experiment(
            mode=exp.mode,
            primary_metric=primary_metric,
            variants=variants_dicts,
            snapshots_by_variant=snaps_by_variant,
            min_criteria=min_criteria,
        )

        # Persist evaluation (append-only)
        per_variant = {
            r.variant_id: {
                "is_control": r.is_control,
                "metric_value": r.metric_value,
                "relative_diff": r.relative_diff,
                "confidence": r.confidence,
                "aggregated": r.aggregated,
            }
            for r in eval_result.variant_results
        }

        evaluation = ExperimentEvaluation(
            organization_id=org_id,
            experiment_id=experiment_id,
            evaluated_at=datetime.now(UTC),
            evaluation_state=eval_result.evaluation_state,
            primary_metric=primary_metric,
            per_variant_result=per_variant,
            confidence=eval_result.confidence,
            data_window=eval_result.data_window,
            matured_through=date.today(),
            limitations=eval_result.limitations,
            total_snapshots_used=sum(len(s) for s in snaps_by_variant.values()),
            engine_version=eval_result.engine_version,
            causal_attribution=eval_result.causal_attribution,
            notes=notes or eval_result.notes,
        )
        db.add(evaluation)

        # Update experiment evaluation_state
        exp.evaluation_state = eval_result.evaluation_state
        if exp.status == "running":
            exp.status = "evaluating"

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="experiment_evaluated",
            entity_type="experiment_evaluation",
            entity_id=str(experiment_id),
            payload={
                "evaluation_state": eval_result.evaluation_state,
                "confidence": eval_result.confidence,
                "primary_metric": primary_metric,
                "limitations_count": len(eval_result.limitations),
            },
            result="success",
        )
        db.add(log)
        await db.commit()
        await db.refresh(evaluation)
        return evaluation

    async def list_evaluations(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> list[ExperimentEvaluation]:
        result = await db.execute(
            select(ExperimentEvaluation)
            .where(
                ExperimentEvaluation.experiment_id == experiment_id,
                ExperimentEvaluation.organization_id == org_id,
            )
            .order_by(ExperimentEvaluation.evaluated_at.desc())
        )
        return list(result.scalars().all())


def _build_criteria(exp: Experiment, settings: Settings) -> dict:
    base = {
        "min_spend": settings.exp_default_min_spend,
        "min_impressions": settings.exp_default_min_impressions,
        "min_clicks": settings.exp_default_min_clicks,
        "min_conversions": settings.exp_default_min_conversions,
        "min_days": settings.exp_default_min_days,
        "min_difference": settings.exp_default_min_difference,
        "min_confidence": settings.exp_default_min_confidence,
        "max_frequency": settings.exp_default_max_frequency,
        "maturation_window_days": settings.exp_default_maturation_window_days,
    }
    if exp.min_criteria:
        base.update({k: v for k, v in exp.min_criteria.items() if v is not None})
    # Legacy fields
    if exp.min_spend:
        base["min_spend"] = exp.min_spend
    if exp.min_impressions:
        base["min_impressions"] = exp.min_impressions
    if exp.min_days:
        base["min_days"] = exp.min_days
    return base
