"""
Learnings router — lifecycle management for learnings.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, get_current_user, require_roles
from app.models.user import User
from app.schemas.learning import (
    LearningCreate,
    LearningOut,
    LearningRejectRequest,
    LearningReviewRequest,
)
from app.services.learning_service import LearningService

router = APIRouter()


def _svc():
    return LearningService(get_settings())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=LearningOut)
async def create_learning(
    data: LearningCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin", "editor"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    try:
        learning = await _svc().create(db, org_id, user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return learning


@router.get("", response_model=list[LearningOut])
async def list_learnings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    learn_status: str | None = Query(None, alias="status"),
    product_id: uuid.UUID | None = None,
    segment: str | None = None,
    objective: str | None = None,
    placement: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    learnings, _ = await _svc().list(
        db, org_id,
        status=learn_status,
        product_id=product_id,
        segment=segment,
        objective=objective,
        placement=placement,
        page=page,
        page_size=page_size,
    )
    return learnings


@router.get("/{learning_id}", response_model=LearningOut)
async def get_learning(
    learning_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    learning = await _svc().get(db, org_id, learning_id)
    if not learning:
        raise HTTPException(status_code=404, detail="Learning not found.")
    return learning


@router.post("/{learning_id}/confirm", response_model=LearningOut)
async def confirm_learning(
    learning_id: uuid.UUID,
    body: LearningReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    try:
        learning = await _svc().confirm(db, org_id, user.id, learning_id, comment=body.comment)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return learning


@router.post("/{learning_id}/reject", response_model=LearningOut)
async def reject_learning(
    learning_id: uuid.UUID,
    body: LearningRejectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_roles("owner", "admin"))],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
):
    try:
        learning = await _svc().reject(db, org_id, user.id, learning_id, comment=body.comment)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return learning
