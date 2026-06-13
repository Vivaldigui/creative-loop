from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, get_current_user
from app.models.analysis import CreativeAnalysis
from app.models.source_ad import PerformanceSnapshot, SourceAd
from app.models.user import User

router = APIRouter()


# ── Output schemas ────────────────────────────────────────────────

class SnapshotOut(BaseModel):
    id: uuid.UUID
    date_start: str | None
    date_stop: str | None
    impressions: int | None
    reach: int | None
    spend: float | None
    clicks: int | None
    link_clicks: int | None
    ctr: float | None
    cpc: float | None
    cpm: float | None
    purchases: int | None
    leads: int | None
    adds_to_cart: int | None
    landing_page_views: int | None
    purchase_value: float | None
    roas: float | None
    roas_source: str | None
    currency: str | None
    attribution_window: str | None
    level: str | None
    normalization_version: str | None
    is_fictitious: bool

    model_config = {"from_attributes": True}


class CreativeOut(BaseModel):
    id: uuid.UUID
    external_id: str
    name: str | None
    title: str | None
    body: str | None
    cta_type: str | None
    link_url: str | None
    image_hash: str | None
    image_url: str | None
    source: str | None

    model_config = {"from_attributes": True}


class AdSetOut(BaseModel):
    id: uuid.UUID
    external_id: str
    name: str
    optimization_goal: str | None
    effective_status: str | None

    model_config = {"from_attributes": True}


class SourceAdOut(BaseModel):
    id: uuid.UUID
    external_id: str | None
    name: str
    headline: str | None
    body_text: str | None
    cta: str | None
    ad_format: str | None
    placement: str | None
    objective: str | None
    status: str
    effective_status: str | None
    configured_status: str | None
    performance_label: str | None
    is_fictitious: bool
    source: str | None
    last_synced_at: Any
    snapshots: list[SnapshotOut] = []
    source_adset: AdSetOut | None = None
    source_creative: CreativeOut | None = None

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    id: uuid.UUID
    source_ad_id: uuid.UUID
    provider: str
    model_used: str | None
    status: str
    analysis_version: int
    media_kind: str | None
    visual_summary: str | None
    observations: Any
    metric_facts: Any
    limitations: Any
    strengths: Any
    weaknesses: Any
    performance_hypotheses: Any
    elements_to_test: Any
    policy_risks: Any
    confidence: float | None
    is_fictitious: bool
    repaired: bool
    estimated_cost_usd: float | None
    latency_ms: int | None

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("")
async def list_source_ads(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    performance_label: str | None = Query(default=None),
    source: str | None = Query(default=None),
    objective: str | None = Query(default=None),
    effective_status: str | None = Query(default=None),
    is_fictitious: bool | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SourceAdOut]:
    q = (
        select(SourceAd)
        .where(SourceAd.organization_id == org_id)
        .options(
            selectinload(SourceAd.snapshots),
            selectinload(SourceAd.source_adset),
            selectinload(SourceAd.source_creative),
        )
        .order_by(SourceAd.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if performance_label is not None:
        q = q.where(SourceAd.performance_label == performance_label)
    if source is not None:
        q = q.where(SourceAd.source == source)
    if objective is not None:
        q = q.where(SourceAd.objective == objective)
    if effective_status is not None:
        q = q.where(SourceAd.effective_status == effective_status)
    if is_fictitious is not None:
        q = q.where(SourceAd.is_fictitious == is_fictitious)

    result = await db.execute(q)
    return [SourceAdOut.model_validate(ad) for ad in result.scalars().all()]


@router.get("/{ad_id}")
async def get_source_ad(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> SourceAdOut:
    result = await db.execute(
        select(SourceAd)
        .where(SourceAd.id == ad_id, SourceAd.organization_id == org_id)
        .options(
            selectinload(SourceAd.snapshots),
            selectinload(SourceAd.source_adset),
            selectinload(SourceAd.source_creative),
        )
    )
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return SourceAdOut.model_validate(ad)


@router.get("/{ad_id}/insights")
async def get_ad_insights(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    limit: int = Query(default=90, le=365),
) -> list[SnapshotOut]:
    result = await db.execute(
        select(PerformanceSnapshot)
        .where(
            PerformanceSnapshot.source_ad_id == ad_id,
            PerformanceSnapshot.organization_id == org_id,
        )
        .order_by(PerformanceSnapshot.date_start.asc())
        .limit(limit)
    )
    return [SnapshotOut.model_validate(s) for s in result.scalars().all()]


class AnalyzeAdRequest(BaseModel):
    force: bool = False


@router.post("/{ad_id}/analyze")
async def analyze_ad(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
    body: AnalyzeAdRequest = AnalyzeAdRequest(),
) -> AnalysisOut:
    from app.services.analysis_service import AnalysisService

    settings = get_settings()
    service = AnalysisService(
        db=db,
        org_id=org_id,
        actor_id=current_user.id,
        provider=settings.anthropic_provider,
        model=settings.anthropic_model,
        timeout_s=settings.anthropic_timeout_s,
        max_retries=settings.anthropic_max_retries,
        max_image_bytes=int(settings.anthropic_max_image_mb * 1_048_576),
        price_input_per_mtok=settings.anthropic_price_input_per_mtok,
        price_output_per_mtok=settings.anthropic_price_output_per_mtok,
    )
    analysis = await service.analyze(ad_id, force=body.force)
    return AnalysisOut.model_validate(analysis)


@router.get("/{ad_id}/analyses")
async def list_ad_analyses(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AnalysisOut]:
    result = await db.execute(
        select(CreativeAnalysis)
        .where(
            CreativeAnalysis.source_ad_id == ad_id,
            CreativeAnalysis.organization_id == org_id,
        )
        .order_by(CreativeAnalysis.analysis_version.desc())
        .limit(limit)
        .offset(offset)
    )
    return [AnalysisOut.model_validate(a) for a in result.scalars().all()]
