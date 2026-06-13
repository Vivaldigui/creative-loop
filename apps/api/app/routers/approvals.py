"""
Approval queue — GET /approvals, GET /approvals/{id}.

Shows creatives awaiting human review (status: awaiting_approval or blocked).
Provides full context for the reviewer: image, checks, prompt, cost.
"""
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
from app.models.creative import GeneratedCreative
from app.models.creative_asset import CreativeAsset
from app.models.user import User

router = APIRouter()

REVIEW_STATUSES = ("awaiting_approval", "blocked")


# ── Schemas ────────────────────────────────────────────────────────

class CheckSummary(BaseModel):
    id: uuid.UUID
    result: str
    findings_count: int
    has_blocked: bool
    has_warning: bool
    checker_types: list[str]


class ApprovalQueueItem(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    model_used: str | None
    storage_key: str | None
    file_hash: str | None
    width: int | None
    height: int | None
    is_fictitious: bool
    estimated_cost_usd: float | None
    variation_of_id: uuid.UUID | None
    source_ad_id: uuid.UUID | None
    quality_check: CheckSummary | None
    policy_check: CheckSummary | None
    thumbnail_url: str | None
    created_at: str | None

    model_config = {"from_attributes": True}


class ApprovalDetailOut(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    model_used: str | None
    parameters: dict | None
    file_hash: str | None
    phash: str | None
    width: int | None
    height: int | None
    estimated_cost_usd: float | None
    is_fictitious: bool
    variation_of_id: uuid.UUID | None
    source_ad_id: uuid.UUID | None

    # Prompt info
    prompt_version_id: uuid.UUID
    prompt_text: str | None
    prompt_version_number: int | None
    prompt_diff_summary: str | None
    prompt_change_reason: str | None
    prompt_learning_used: str | None

    # Checks
    quality_checks: list[dict]
    policy_checks: list[dict]

    # Assets (with signed URLs)
    assets: list[dict]

    # Notice (never claim Meta approval)
    internal_notice: str = (
        "Verificação interna concluída. Isto NÃO garante aprovação pela Meta Ads "
        "ou qualquer outra plataforma."
    )

    created_at: str | None


# ── Helpers ────────────────────────────────────────────────────────

def _thumbnail_url(creative: GeneratedCreative, settings: Any) -> str | None:
    from packages.storage.local import LocalStorage

    for asset in getattr(creative, "assets", []):
        if asset.role == "thumbnail" and asset.storage_key and asset.storage_backend == "local":
            try:
                ls = LocalStorage(
                    base_dir=settings.storage_local_dir,
                    secret_key=settings.secret_key,
                )
                return ls.signed_url(
                    str(asset.organization_id),
                    asset.storage_key,
                    ttl=settings.signed_url_ttl_seconds,
                )
            except Exception:
                pass
    return None


def _summarise_check(checks: list[Any]) -> CheckSummary | None:
    if not checks:
        return None
    latest = checks[-1]
    findings = (latest.findings or {}).get("findings", [])
    checker_types = list({f.get("checker_type", "deterministic") for f in findings})
    return CheckSummary(
        id=latest.id,
        result=latest.result,
        findings_count=len(findings),
        has_blocked=any(f.get("severity") == "blocked" for f in findings),
        has_warning=any(f.get("severity") == "warning" for f in findings),
        checker_types=checker_types,
    )


def _asset_out(asset: CreativeAsset, settings: Any) -> dict:
    signed_url: str | None = None
    if asset.storage_backend == "local" and asset.storage_key:
        from packages.storage.local import LocalStorage
        try:
            ls = LocalStorage(
                base_dir=settings.storage_local_dir,
                secret_key=settings.secret_key,
            )
            signed_url = ls.signed_url(
                str(asset.organization_id),
                asset.storage_key,
                ttl=settings.signed_url_ttl_seconds,
            )
        except Exception:
            pass
    return {
        "id": str(asset.id),
        "role": asset.role,
        "format_label": asset.format_label,
        "width": asset.width,
        "height": asset.height,
        "file_size_bytes": asset.file_size_bytes,
        "file_hash": asset.file_hash,
        "fit_strategy": asset.fit_strategy,
        "signed_url": signed_url,
    }


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("")
async def list_approvals(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_blocked: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ApprovalQueueItem]:
    settings = get_settings()
    statuses = list(REVIEW_STATUSES) if include_blocked else ["awaiting_approval"]

    q = (
        select(GeneratedCreative)
        .options(
            selectinload(GeneratedCreative.assets),
            selectinload(GeneratedCreative.quality_checks),
            selectinload(GeneratedCreative.policy_checks),
        )
        .where(
            GeneratedCreative.organization_id == org_id,
            GeneratedCreative.status.in_(statuses),
        )
        .order_by(GeneratedCreative.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(q)
    creatives = result.scalars().all()

    items: list[ApprovalQueueItem] = []
    for c in creatives:
        items.append(ApprovalQueueItem(
            id=c.id,
            status=c.status,
            provider=c.provider,
            model_used=c.model_used,
            storage_key=c.storage_key,
            file_hash=c.file_hash,
            width=c.width,
            height=c.height,
            is_fictitious=c.is_fictitious,
            estimated_cost_usd=c.estimated_cost_usd,
            variation_of_id=c.variation_of_id,
            source_ad_id=c.source_ad_id,
            quality_check=_summarise_check(list(c.quality_checks)),
            policy_check=_summarise_check(list(c.policy_checks)),
            thumbnail_url=_thumbnail_url(c, settings),
            created_at=c.created_at.isoformat() if c.created_at else None,
        ))
    return items


@router.get("/{creative_id}")
async def get_approval_detail(
    creative_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApprovalDetailOut:
    settings = get_settings()
    result = await db.execute(
        select(GeneratedCreative)
        .options(
            selectinload(GeneratedCreative.assets),
            selectinload(GeneratedCreative.quality_checks),
            selectinload(GeneratedCreative.policy_checks),
            selectinload(GeneratedCreative.prompt_version),
        )
        .where(
            GeneratedCreative.id == creative_id,
            GeneratedCreative.organization_id == org_id,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Creative not found")

    pv = c.prompt_version

    return ApprovalDetailOut(
        id=c.id,
        status=c.status,
        provider=c.provider,
        model_used=c.model_used,
        parameters=c.parameters,
        file_hash=c.file_hash,
        phash=c.phash,
        width=c.width,
        height=c.height,
        estimated_cost_usd=c.estimated_cost_usd,
        is_fictitious=c.is_fictitious,
        variation_of_id=c.variation_of_id,
        source_ad_id=c.source_ad_id,
        prompt_version_id=c.prompt_version_id,
        prompt_text=pv.prompt_text if pv else None,
        prompt_version_number=pv.version_number if pv else None,
        prompt_diff_summary=pv.diff_summary if pv else None,
        prompt_change_reason=pv.change_reason if pv else None,
        prompt_learning_used=pv.learning_used if pv else None,
        quality_checks=[
            {**qc.findings, "result": qc.result, "id": str(qc.id)}
            for qc in c.quality_checks
        ],
        policy_checks=[
            {**pc.findings, "result": pc.result, "id": str(pc.id), "rule_set_version": pc.rule_set_version}
            for pc in c.policy_checks
        ],
        assets=[_asset_out(a, settings) for a in c.assets],
        created_at=c.created_at.isoformat() if c.created_at else None,
    )
