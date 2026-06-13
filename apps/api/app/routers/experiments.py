"""
Experiments router — full CRUD + lifecycle for experiments and variants.

Endpoints:
    POST   /experiments
    GET    /experiments
    GET    /experiments/{id}
    POST   /experiments/{id}/start
    POST   /experiments/{id}/evaluate
    POST   /experiments/{id}/complete
    POST   /experiments/{id}/stop
    GET    /experiments/{id}/metrics
    GET    /experiments/{id}/decisions
    POST   /experiments/{id}/decisions
    GET    /experiments/{id}/evaluations
    POST   /experiments/{id}/suggest-next-round
    GET    /experiments/{id}/suggestions
    GET    /suggestions
    GET    /suggestions/{id}
    POST   /suggestions/{id}/approve
    POST   /suggestions/{id}/reject
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, get_current_user, require_roles
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.experiment import (
    DecisionCreate,
    DecisionOut,
    EvaluationOut,
    EvaluationRequest,
    ExperimentCreate,
    ExperimentOut,
    ExperimentStartRequest,
    ExperimentStopRequest,
    VariantSnapshotOut,
)
from app.schemas.suggestion import SuggestionOut, SuggestionReviewRequest
from app.services.decision_service import DecisionService
from app.services.evaluation_service import EvaluationService
from app.services.experiment_service import ExperimentService
from app.services.next_round_service import NextRoundService

router = APIRouter()
suggestions_router = APIRouter()


def _get_services():
    s = get_settings()
    return ExperimentService(s), EvaluationService(s), DecisionService(s), NextRoundService(s)


# ── Experiments CRUD ───────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ExperimentOut)
async def create_experiment(
    data: ExperimentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    svc, _, _, _ = _get_services()
    try:
        exp = await svc.create(db, org_id, user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return exp


@router.get("", response_model=PaginatedResponse)
async def list_experiments(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    exp_status: str | None = Query(None, alias="status"),
    mode: str | None = None,
    product_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc, _, _, _ = _get_services()
    items, total = await svc.list(db, org_id, status=exp_status, mode=mode, product_id=product_id, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[ExperimentOut.model_validate(e) for e in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{experiment_id}", response_model=ExperimentOut)
async def get_experiment(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    svc, _, _, _ = _get_services()
    exp = await svc.get(db, org_id, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return exp


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@router.post("/{experiment_id}/start", response_model=ExperimentOut)
async def start_experiment(
    experiment_id: uuid.UUID,
    body: ExperimentStartRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    if not body.confirm:
        raise HTTPException(status_code=422, detail="Set confirm=true to start the experiment.")
    svc, _, _, _ = _get_services()
    try:
        exp = await svc.start(db, org_id, user.id, experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return exp


@router.post("/{experiment_id}/stop", response_model=ExperimentOut)
async def stop_experiment(
    experiment_id: uuid.UUID,
    body: ExperimentStopRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    svc, _, _, _ = _get_services()
    try:
        exp = await svc.stop(db, org_id, user.id, experiment_id, stop_reason=body.stop_reason, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return exp


@router.post("/{experiment_id}/complete", response_model=ExperimentOut)
async def complete_experiment(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    svc, _, _, _ = _get_services()
    try:
        exp = await svc.complete(db, org_id, user.id, experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return exp


# ── Evaluation ────────────────────────────────────────────────────────────────

@router.post("/{experiment_id}/evaluate", response_model=EvaluationOut, status_code=201)
async def evaluate_experiment(
    experiment_id: uuid.UUID,
    body: EvaluationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    _, eval_svc, _, _ = _get_services()
    try:
        evaluation = await eval_svc.evaluate(db, org_id, user.id, experiment_id, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return evaluation


@router.get("/{experiment_id}/evaluations", response_model=list[EvaluationOut])
async def list_evaluations(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    _, eval_svc, _, _ = _get_services()
    return await eval_svc.list_evaluations(db, org_id, experiment_id)


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/{experiment_id}/metrics", response_model=list[VariantSnapshotOut])
async def get_experiment_metrics(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    variant_id: uuid.UUID | None = None,
    date_start: str | None = None,
    date_stop: str | None = None,
):
    from app.models.variant_metric import VariantPerformanceSnapshot
    q = select(VariantPerformanceSnapshot).where(
        VariantPerformanceSnapshot.experiment_id == experiment_id,
        VariantPerformanceSnapshot.organization_id == org_id,
    )
    if variant_id:
        q = q.where(VariantPerformanceSnapshot.variant_id == variant_id)
    if date_start:
        q = q.where(VariantPerformanceSnapshot.date_start >= date_start)
    if date_stop:
        q = q.where(VariantPerformanceSnapshot.date_stop <= date_stop)
    q = q.order_by(VariantPerformanceSnapshot.date_start.desc())
    result = await db.execute(q)
    return result.scalars().all()


# ── Decisions ─────────────────────────────────────────────────────────────────

@router.post("/{experiment_id}/decisions", response_model=DecisionOut, status_code=201)
async def create_decision(
    experiment_id: uuid.UUID,
    data: DecisionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    _, _, dec_svc, _ = _get_services()
    try:
        decision = await dec_svc.create(
            db, org_id, user.id, experiment_id,
            evaluation_id=data.evaluation_id,
            primary_metric=data.primary_metric,
            recommendation=data.recommendation,
            suggested_action=data.suggested_action,
            executed_action=data.executed_action,
            execution_notes=data.execution_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return decision


@router.get("/{experiment_id}/decisions", response_model=list[DecisionOut])
async def list_decisions(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    _, _, dec_svc, _ = _get_services()
    return await dec_svc.list_for_experiment(db, org_id, experiment_id)


# ── Next round suggestions ─────────────────────────────────────────────────────

@router.post("/{experiment_id}/suggest-next-round", response_model=SuggestionOut, status_code=201)
async def suggest_next_round(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    _, _, _, sug_svc = _get_services()
    try:
        suggestion = await sug_svc.suggest(db, org_id, user.id, experiment_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return suggestion


@router.get("/{experiment_id}/suggestions", response_model=list[SuggestionOut])
async def list_experiment_suggestions(
    experiment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    _, _, _, sug_svc = _get_services()
    return await sug_svc.list_for_experiment(db, org_id, experiment_id)


# ── Suggestions resource (root) ────────────────────────────────────────────────

@suggestions_router.get("/suggestions", response_model=list[SuggestionOut])
async def list_all_suggestions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    sug_status: str | None = Query(None, alias="status"),
):
    sug_svc = NextRoundService(get_settings())
    return await sug_svc.list(db, org_id, status=sug_status)


@suggestions_router.get("/suggestions/{suggestion_id}", response_model=SuggestionOut)
async def get_suggestion(
    suggestion_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    sug_svc = NextRoundService(get_settings())
    sug = await sug_svc.get(db, org_id, suggestion_id)
    if not sug:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return sug


@suggestions_router.post("/suggestions/{suggestion_id}/approve", response_model=SuggestionOut)
async def approve_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    sug_svc = NextRoundService(get_settings())
    try:
        sug = await sug_svc.approve(db, org_id, user.id, suggestion_id, comment=body.comment)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return sug


@suggestions_router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionOut)
async def reject_suggestion(
    suggestion_id: uuid.UUID,
    body: SuggestionReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    sug_svc = NextRoundService(get_settings())
    try:
        sug = await sug_svc.reject(db, org_id, user.id, suggestion_id, comment=body.comment)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return sug
