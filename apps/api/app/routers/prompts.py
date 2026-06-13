"""
/prompts  — PromptTemplate CRUD + versioning (Phase 3)

Endpoints:
  POST /prompts/generate            create template + v1
  GET  /prompts                     list templates
  GET  /prompts/{id}                template detail + latest version
  POST /prompts/{id}/revise         create new version (id = template_id)
  GET  /prompts/{id}/versions       all versions for a template
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.deps import get_current_org, get_current_user
from app.models.prompt import PromptTemplate, PromptVersion
from app.models.user import User

router = APIRouter()


# ── Output schemas ────────────────────────────────────────────────

class PromptVersionOut(BaseModel):
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


class PromptTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    product_id: uuid.UUID | None
    hypothesis_id: uuid.UUID | None
    ad_format: str | None
    objective: str | None
    status: str
    created_at: Any

    model_config = {"from_attributes": True}


class PromptTemplateDetailOut(PromptTemplateOut):
    latest_version: PromptVersionOut | None
    version_count: int


# ── Request bodies ────────────────────────────────────────────────

class GeneratePromptRequest(BaseModel):
    source_ad_id: uuid.UUID | None = None
    analysis_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    hypothesis_id: uuid.UUID | None = None
    hypothesis_payload: dict[str, Any] | None = None
    fields: dict[str, Any] | None = None
    ad_format: str = "feed"
    objective: str | None = None
    template_name: str | None = None
    author_type: str = "human"
    target_model: str | None = None
    generation_parameters: dict[str, Any] | None = None


class RevisePromptRequest(BaseModel):
    fields: dict[str, Any]
    change_reason: str
    base_version_id: uuid.UUID | None = None
    author_type: str = "human"
    target_model: str | None = None
    generation_parameters: dict[str, Any] | None = None


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/generate", status_code=status.HTTP_201_CREATED, response_model=PromptVersionOut)
async def generate_prompt(
    body: GeneratePromptRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PromptVersionOut:
    from app.services.prompt_service import PromptService

    service = PromptService(db=db, org_id=org_id, actor_id=current_user.id)
    pv = await service.generate(
        fields=body.fields or {},
        ad_format=body.ad_format,
        objective=body.objective,
        template_name=body.template_name,
        source_ad_id=body.source_ad_id,
        analysis_id=body.analysis_id,
        product_id=body.product_id,
        hypothesis_id=body.hypothesis_id,
        hypothesis_payload=body.hypothesis_payload,
        author_type=body.author_type,
        target_model=body.target_model,
        generation_parameters=body.generation_parameters,
    )
    return PromptVersionOut.model_validate(pv)


@router.get("", response_model=list[PromptTemplateOut])
async def list_prompts(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    product_id: uuid.UUID | None = Query(default=None),
    objective: str | None = Query(default=None),
    ad_format: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PromptTemplateOut]:
    q = (
        select(PromptTemplate)
        .where(PromptTemplate.organization_id == org_id)
        .order_by(PromptTemplate.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if product_id:
        q = q.where(PromptTemplate.product_id == product_id)
    if objective:
        q = q.where(PromptTemplate.objective == objective)
    if ad_format:
        q = q.where(PromptTemplate.ad_format == ad_format)
    result = await db.execute(q)
    return [PromptTemplateOut.model_validate(t) for t in result.scalars().all()]


@router.get("/{template_id}", response_model=PromptTemplateDetailOut)
async def get_prompt(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> PromptTemplateDetailOut:
    result = await db.execute(
        select(PromptTemplate)
        .where(
            PromptTemplate.id == template_id,
            PromptTemplate.organization_id == org_id,
        )
        .options(selectinload(PromptTemplate.versions))
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    latest = max(tmpl.versions, key=lambda v: v.version_number, default=None)
    return PromptTemplateDetailOut(
        id=tmpl.id,
        name=tmpl.name,
        product_id=tmpl.product_id,
        hypothesis_id=tmpl.hypothesis_id,
        ad_format=tmpl.ad_format,
        objective=tmpl.objective,
        status=tmpl.status,
        created_at=tmpl.created_at,
        latest_version=PromptVersionOut.model_validate(latest) if latest else None,
        version_count=len(tmpl.versions),
    )


@router.post("/{template_id}/revise", status_code=status.HTTP_201_CREATED, response_model=PromptVersionOut)
async def revise_prompt(
    template_id: uuid.UUID,
    body: RevisePromptRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PromptVersionOut:
    from app.services.prompt_service import PromptService

    service = PromptService(db=db, org_id=org_id, actor_id=current_user.id)
    pv = await service.revise(
        template_id=template_id,
        fields=body.fields,
        change_reason=body.change_reason,
        base_version_id=body.base_version_id,
        author_type=body.author_type,
        target_model=body.target_model,
        generation_parameters=body.generation_parameters,
    )
    return PromptVersionOut.model_validate(pv)


@router.get("/{template_id}/versions", response_model=list[PromptVersionOut])
async def list_prompt_versions(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PromptVersionOut]:
    result = await db.execute(
        select(PromptVersion)
        .where(
            PromptVersion.template_id == template_id,
            PromptVersion.organization_id == org_id,
        )
        .order_by(PromptVersion.version_number.asc())
        .limit(limit)
        .offset(offset)
    )
    return [PromptVersionOut.model_validate(pv) for pv in result.scalars().all()]
