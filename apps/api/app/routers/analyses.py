"""
GET /analyses/{id}  — retrieve a single analysis (Phase 3)
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_org
from app.models.analysis import CreativeAnalysis

router = APIRouter()


class AnalysisDetailOut(BaseModel):
    id: uuid.UUID
    source_ad_id: uuid.UUID
    provider: str
    model_used: str | None
    status: str
    analysis_version: int
    media_kind: str | None
    input_hash: str | None
    visual_summary: str | None
    observations: Any
    metric_facts: Any
    limitations: Any
    composition: Any
    hierarchy: Any
    product_presentation: Any
    color_and_lighting: Any
    text_analysis: Any
    attention_elements: Any
    strengths: Any
    weaknesses: Any
    performance_hypotheses: Any
    elements_to_preserve: Any
    elements_to_test: Any
    policy_risks: Any
    confidence: float | None
    is_fictitious: bool
    repaired: bool
    request_metadata: Any
    parameters: Any
    prompt_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    latency_ms: int | None
    created_at: Any

    model_config = {"from_attributes": True}


@router.get("/{analysis_id}", response_model=AnalysisDetailOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> AnalysisDetailOut:
    result = await db.execute(
        select(CreativeAnalysis).where(
            CreativeAnalysis.id == analysis_id,
            CreativeAnalysis.organization_id == org_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisDetailOut.model_validate(analysis)
