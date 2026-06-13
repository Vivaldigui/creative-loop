"""
ExperimentService — CRUD + lifecycle for Experiment and ExperimentVariant.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from packages.experiment_engine.guards import (
    ExperimentGuardContext,
    has_blocking_failure,
    run_experiment_guards,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models.audit import AuditLog
from app.models.experiment import Experiment, ExperimentVariant
from app.schemas.experiment import ExperimentCreate

logger = structlog.get_logger()


class ExperimentService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: ExperimentCreate,
    ) -> Experiment:
        # Validate mode constraints before creation
        variants_data = data.variants or []
        ctx = _build_guard_context(data.mode, data.primary_variable, variants_data, data.planned_budget, self._settings)
        guard_results = run_experiment_guards(ctx)
        if has_blocking_failure(guard_results):
            blocked = [r for r in guard_results if r.severity == "blocked"]
            detail = "; ".join(r.detail for r in blocked)
            raise ValueError(f"Experiment validation failed: {detail}")

        min_criteria = data.min_criteria.model_dump(exclude_none=True) if data.min_criteria else None

        exp = Experiment(
            organization_id=org_id,
            name=data.name,
            mode=data.mode,
            hypothesis=data.hypothesis,
            primary_variable=data.primary_variable,
            status="draft",
            objective=data.objective,
            product_id=data.product_id,
            audience=data.audience,
            placement=data.placement,
            window_start=data.window_start,
            window_end=data.window_end,
            planned_budget=data.planned_budget,
            currency=data.currency or self._settings.default_currency,
            primary_metric=data.primary_metric,
            secondary_metrics=data.secondary_metrics,
            min_criteria=min_criteria,
            is_fictitious=data.is_fictitious,
        )
        db.add(exp)
        await db.flush()

        for v in variants_data:
            variant = ExperimentVariant(
                organization_id=org_id,
                experiment_id=exp.id,
                name=v.name,
                hypothesis=v.hypothesis,
                is_control=v.is_control,
                variant_role="control" if v.is_control else "test",
                status="draft",
                creative_id=v.creative_id,
                prompt_version_id=v.prompt_version_id,
                published_ad_id=v.published_ad_id,
                changed_variables=v.changed_variables,
                allocated_budget=v.allocated_budget,
                is_fictitious=data.is_fictitious,
            )
            db.add(variant)

        await db.flush()

        # Set baseline_variant_id to the control variant
        result = await db.execute(
            select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == exp.id,
                ExperimentVariant.is_control == True,  # noqa: E712
            ).limit(1)
        )
        ctrl = result.scalar_one_or_none()
        if ctrl:
            exp.baseline_variant_id = ctrl.id

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="experiment_created",
            entity_type="experiment",
            entity_id=str(exp.id),
            payload={"name": data.name, "mode": data.mode},
            result="success",
        )
        db.add(log)
        await db.commit()
        return await self.get(db, org_id, exp.id)  # re-query with selectinload

    async def get(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> Experiment | None:
        result = await db.execute(
            select(Experiment)
            .where(Experiment.id == experiment_id, Experiment.organization_id == org_id)
            .options(selectinload(Experiment.variants))
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        status: str | None = None,
        mode: str | None = None,
        product_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Experiment], int]:
        q = select(Experiment).where(Experiment.organization_id == org_id)
        if status:
            q = q.where(Experiment.status == status)
        if mode:
            q = q.where(Experiment.mode == mode)
        if product_id:
            q = q.where(Experiment.product_id == product_id)

        from sqlalchemy import func
        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar_one()

        q = q.order_by(Experiment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        q = q.options(selectinload(Experiment.variants))
        rows = (await db.execute(q)).scalars().all()
        return list(rows), total

    async def start(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> Experiment:
        exp = await self.get(db, org_id, experiment_id)
        if not exp:
            raise ValueError("Experiment not found.")
        if exp.status not in ("draft", "scheduled"):
            raise ValueError(f"Cannot start experiment in status '{exp.status}'.")

        # Re-run guards on start
        variants_data = [_variant_to_dict(v) for v in exp.variants]
        ctx = _build_guard_context_from_exp(exp, variants_data, self._settings)
        guard_results = run_experiment_guards(ctx)
        if has_blocking_failure(guard_results):
            blocked = [r for r in guard_results if r.severity == "blocked"]
            detail = "; ".join(r.detail for r in blocked)
            raise ValueError(f"Cannot start: {detail}")

        exp.status = "running"
        exp.started_at = datetime.now(UTC)

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="experiment_started",
            entity_type="experiment",
            entity_id=str(exp.id),
            result="success",
        )
        db.add(log)
        await db.commit()
        return await self.get(db, org_id, experiment_id)

    async def stop(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
        stop_reason: str = "manual",
        notes: str | None = None,
    ) -> Experiment:
        exp = await self.get(db, org_id, experiment_id)
        if not exp:
            raise ValueError("Experiment not found.")
        if exp.status in ("completed", "stopped"):
            raise ValueError(f"Experiment already {exp.status}.")

        exp.status = "stopped"
        exp.stop_reason = stop_reason
        exp.ended_at = datetime.now(UTC)

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="experiment_stopped",
            entity_type="experiment",
            entity_id=str(exp.id),
            payload={"stop_reason": stop_reason, "notes": notes},
            result="success",
        )
        db.add(log)
        await db.commit()
        return await self.get(db, org_id, experiment_id)

    async def complete(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
        stop_reason: str = "winner_candidate",
    ) -> Experiment:
        exp = await self.get(db, org_id, experiment_id)
        if not exp:
            raise ValueError("Experiment not found.")

        exp.status = "completed"
        exp.stop_reason = stop_reason
        exp.ended_at = datetime.now(UTC)

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="experiment_completed",
            entity_type="experiment",
            entity_id=str(exp.id),
            payload={"stop_reason": stop_reason},
            result="success",
        )
        db.add(log)
        await db.commit()
        return await self.get(db, org_id, experiment_id)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _variant_to_dict(v: ExperimentVariant) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "name": v.name,
        "is_control": v.is_control,
        "hypothesis": v.hypothesis,
        "changed_variables": v.changed_variables or [],
        "allocated_budget": v.allocated_budget,
        "audience": None,
    }


def _build_guard_context(
    mode: str,
    primary_variable: str | None,
    variants_data: list[Any],
    planned_budget: float | None,
    settings: Settings,
) -> ExperimentGuardContext:
    from app.schemas.experiment import VariantCreate
    vdicts = []
    has_baseline = False
    for v in variants_data:
        if isinstance(v, VariantCreate):
            d = {
                "id": "new",
                "name": v.name,
                "is_control": v.is_control,
                "hypothesis": v.hypothesis,
                "changed_variables": v.changed_variables or [],
                "allocated_budget": v.allocated_budget,
                "audience": v.audience,
            }
            if v.is_control:
                has_baseline = True
        else:
            d = v
            if v.get("is_control"):
                has_baseline = True
        vdicts.append(d)

    return ExperimentGuardContext(
        mode=mode,
        primary_variable=primary_variable,
        variants=vdicts,
        has_baseline=has_baseline,
        window_start=None,
        window_end=None,
        planned_budget=planned_budget,
        max_experiment_budget=settings.max_experiment_budget,
    )


def _build_guard_context_from_exp(exp: Experiment, variants_data: list[dict[str, Any]], settings: Settings) -> ExperimentGuardContext:
    has_baseline = any(v.get("is_control") for v in variants_data)
    return ExperimentGuardContext(
        mode=exp.mode,
        primary_variable=exp.primary_variable,
        variants=variants_data,
        has_baseline=has_baseline,
        window_start=str(exp.window_start) if exp.window_start else None,
        window_end=str(exp.window_end) if exp.window_end else None,
        planned_budget=exp.planned_budget,
        max_experiment_budget=settings.max_experiment_budget,
    )
