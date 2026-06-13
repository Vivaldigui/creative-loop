"""
/prompt-versions/{id}
/prompt-versions/{id}/diff/{other_id}
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_org, get_current_user
from app.models.prompt import PromptVersion
from app.models.user import User

router = APIRouter()


class PromptVersionDetailOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    source_ad_id: uuid.UUID | None
    analysis_id: uuid.UUID | None
    parent_version_id: uuid.UUID | None
    version_number: int
    prompt_text: str
    structured_fields: Any
    diff_summary: str | None
    change_reason: str | None
    author_type: str
    content_hash: str | None
    target_model: str | None
    status: str
    is_fictitious: bool
    created_at: Any

    model_config = {"from_attributes": True}


class DiffOut(BaseModel):
    version_a: dict[str, Any]
    version_b: dict[str, Any]
    unified_diff: str
    field_changes: dict[str, Any]
    changed_field_count: int


@router.get("/{version_id}", response_model=PromptVersionDetailOut)
async def get_prompt_version(
    version_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> PromptVersionDetailOut:
    result = await db.execute(
        select(PromptVersion).where(
            PromptVersion.id == version_id,
            PromptVersion.organization_id == org_id,
        )
    )
    pv = result.scalar_one_or_none()
    if pv is None:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return PromptVersionDetailOut.model_validate(pv)


@router.get("/{version_id}/diff/{other_version_id}", response_model=DiffOut)
async def diff_prompt_versions(
    version_id: uuid.UUID,
    other_version_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DiffOut:
    from app.services.prompt_service import PromptService

    service = PromptService(db=db, org_id=org_id, actor_id=current_user.id)
    result = await service.diff(version_id, other_version_id)
    return DiffOut(**result)
