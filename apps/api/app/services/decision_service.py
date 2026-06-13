"""
DecisionService — records OptimizationDecision for an experiment.

v1: only suggests actions; budget never changed automatically.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.audit import AuditLog
from app.models.decision import OptimizationDecision
from app.models.evaluation import ExperimentEvaluation
from app.models.experiment import Experiment

logger = structlog.get_logger()

VALID_ACTIONS = {"continue", "pause", "review", "create_new_hypothesis", "wait_more_data"}


class DecisionService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
        evaluation_id: uuid.UUID | None,
        primary_metric: str | None,
        recommendation: str | None,
        suggested_action: str | None,
        executed_action: str | None = None,
        execution_notes: str | None = None,
    ) -> OptimizationDecision:
        # Guard: no automatic budget changes
        if executed_action and "budget" in (executed_action or "").lower():
            raise ValueError("Budget changes are not allowed via automated decisions. MAX_AUTOMATIC_BUDGET_INCREASE_PERCENT=0.")

        if suggested_action and suggested_action not in VALID_ACTIONS:
            raise ValueError(f"Invalid suggested_action '{suggested_action}'. Valid: {VALID_ACTIONS}")

        # Load experiment for context
        exp_result = await db.execute(
            select(Experiment).where(Experiment.id == experiment_id, Experiment.organization_id == org_id)
        )
        exp = exp_result.scalar_one_or_none()
        if not exp:
            raise ValueError("Experiment not found.")

        # Load evaluation context if provided
        eval_data: dict[str, Any] | None = None
        period_start = period_end = None
        confidence = None
        if evaluation_id:
            eval_result = await db.execute(
                select(ExperimentEvaluation).where(
                    ExperimentEvaluation.id == evaluation_id,
                    ExperimentEvaluation.organization_id == org_id,
                )
            )
            evaluation = eval_result.scalar_one_or_none()
            if evaluation:
                eval_data = {
                    "evaluation_state": evaluation.evaluation_state,
                    "per_variant_result": evaluation.per_variant_result,
                    "limitations": evaluation.limitations,
                    "engine_version": evaluation.engine_version,
                }
                confidence = evaluation.confidence
                if evaluation.data_window:
                    period_start = evaluation.data_window.get("start")
                    period_end = evaluation.data_window.get("end")

        decision = OptimizationDecision(
            organization_id=org_id,
            experiment_id=experiment_id,
            evaluation_id=evaluation_id,
            data_used=eval_data,
            period_start=period_start,
            period_end=period_end,
            primary_metric=primary_metric or exp.primary_metric,
            result=eval_data.get("per_variant_result") if eval_data else None,
            confidence=confidence,
            limitations=eval_data.get("limitations") if eval_data else None,
            recommendation=recommendation,
            suggested_action=suggested_action,
            executed_action=executed_action,
            execution_notes=execution_notes,
            user_responsible_id=actor_id,
            decided_at=datetime.now(UTC),
        )
        db.add(decision)
        await db.flush()

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="optimization_decision_created",
            entity_type="optimization_decision",
            entity_id=str(decision.id),
            payload={
                "experiment_id": str(experiment_id),
                "suggested_action": suggested_action,
                "executed_action": executed_action,
                "recommendation_summary": (recommendation or "")[:200],
            },
            result="success",
        )
        db.add(log)
        decision.audit_log_id = log.id
        await db.commit()
        await db.refresh(decision)
        return decision

    async def list_for_experiment(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> list[OptimizationDecision]:
        result = await db.execute(
            select(OptimizationDecision)
            .where(
                OptimizationDecision.experiment_id == experiment_id,
                OptimizationDecision.organization_id == org_id,
            )
            .order_by(OptimizationDecision.decided_at.desc())
        )
        return list(result.scalars().all())
