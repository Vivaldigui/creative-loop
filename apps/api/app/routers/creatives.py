from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # noqa: F401 – used below

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, get_current_user
from app.models.approval import Approval
from app.models.audit import AuditLog
from app.models.checks import PolicyCheck, QualityCheck
from app.models.creative import GeneratedCreative
from app.models.creative_asset import CreativeAsset
from app.models.prompt import PromptVersion
from app.models.user import User

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────


class GenerateCreativeRequest(BaseModel):
    prompt_version_id: uuid.UUID
    width: int = 1080
    height: int = 1080
    quality: str = "standard"
    n: int = Field(default=1, ge=1, le=4)
    extra_formats: list[str] = []  # e.g. ["1080x1350", "1080x1920"]
    source_ad_id: uuid.UUID | None = None


class CreativeAssetOut(BaseModel):
    id: uuid.UUID
    role: str
    format_label: str | None
    width: int | None
    height: int | None
    file_size_bytes: int | None
    file_hash: str | None
    fit_strategy: str | None
    signed_url: str | None = None

    model_config = {"from_attributes": True}


class CreativeOut(BaseModel):
    id: uuid.UUID
    prompt_version_id: uuid.UUID
    provider: str
    model_used: str | None
    file_path: str | None  # deprecated; populated for local storage backward compat
    storage_key: str | None
    storage_backend: str | None
    file_hash: str | None
    phash: str | None
    width: int | None
    height: int | None
    file_size_bytes: int | None
    mime_type: str | None
    status: str
    is_fictitious: bool
    estimated_cost_usd: float | None
    variation_of_id: uuid.UUID | None
    source_ad_id: uuid.UUID | None
    assets: list[CreativeAssetOut] = []

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    comment: str | None = None
    override_blocked: bool = False  # owner-only: override BLOCKED findings


class RejectRequest(BaseModel):
    comment: str


class RequestVariationRequest(BaseModel):
    comment: str  # required — explain why a new variation is needed
    prompt_version_id: uuid.UUID | None = None  # if None, reuse same version


# ── Helpers ────────────────────────────────────────────────────────


def _signed_url_for_asset(asset: CreativeAsset, settings: Any) -> str | None:
    if not asset.storage_key:
        return None
    try:
        from packages.storage.factory import get_storage

        storage = get_storage(
            asset.storage_backend or settings.storage_backend,
            base_dir=settings.storage_local_dir,
            secret_key=settings.secret_key,
            s3_endpoint=settings.s3_endpoint,
            s3_bucket=settings.s3_bucket,
            s3_access_key=settings.s3_access_key,
            s3_secret_key=settings.s3_secret_key,
            s3_region=settings.s3_region,
        )
        return storage.signed_url(
            str(asset.organization_id),
            asset.storage_key,
            ttl=settings.signed_url_ttl_seconds,
        )
    except Exception:
        return None


def _build_asset_out(asset: CreativeAsset, settings: Any) -> CreativeAssetOut:
    return CreativeAssetOut(
        id=asset.id,
        role=asset.role,
        format_label=asset.format_label,
        width=asset.width,
        height=asset.height,
        file_size_bytes=asset.file_size_bytes,
        file_hash=asset.file_hash,
        fit_strategy=asset.fit_strategy,
        signed_url=_signed_url_for_asset(asset, settings),
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def generate_creative(
    body: GenerateCreativeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CreativeOut:
    settings = get_settings()
    from app.services.creative_service import CreativeService

    svc = CreativeService(
        db=db,
        org_id=org_id,
        actor_id=current_user.id,
        image_provider=settings.image_provider,
        storage_backend=settings.storage_backend,
        storage_dir=settings.storage_local_dir,
        secret_key=settings.secret_key,
        s3_endpoint=settings.s3_endpoint,
        s3_bucket=settings.s3_bucket,
        s3_access_key=settings.s3_access_key,
        s3_secret_key=settings.s3_secret_key,
        s3_region=settings.s3_region,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_image_model,
        openai_timeout_s=settings.openai_timeout_s,
        openai_max_retries=settings.openai_max_retries,
        similarity_threshold=settings.creative_similarity_threshold,
        max_file_mb=settings.creative_max_file_mb,
        thumbnail_max_px=settings.thumbnail_max_px,
        cv_enabled=settings.quality_cv_enabled,
    )
    try:
        creatives = await svc.generate(
            prompt_version_id=body.prompt_version_id,
            base_width=body.width,
            base_height=body.height,
            quality=body.quality,
            n=body.n,
            extra_formats=body.extra_formats,
            source_ad_id=body.source_ad_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if not creatives:
        raise HTTPException(status_code=500, detail="Provider returned no images.")

    # Reload with assets eager-loaded — lazy loading raises MissingGreenlet in async context
    result2 = await db.execute(
        select(GeneratedCreative)
        .options(selectinload(GeneratedCreative.assets))
        .where(GeneratedCreative.id == creatives[0].id)
    )
    c = result2.scalar_one()
    return CreativeOut.model_validate(c)


@router.get("")
async def list_creatives(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    status_filter: str | None = Query(default=None, alias="status"),
    prompt_version_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CreativeOut]:
    q = (
        select(GeneratedCreative)
        .options(selectinload(GeneratedCreative.assets))
        .where(GeneratedCreative.organization_id == org_id)
    )
    if status_filter:
        q = q.where(GeneratedCreative.status == status_filter)
    if prompt_version_id:
        q = q.where(GeneratedCreative.prompt_version_id == prompt_version_id)
    q = q.order_by(GeneratedCreative.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [CreativeOut.model_validate(c) for c in rows]


@router.get("/{creative_id}")
async def get_creative(
    creative_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> CreativeOut:
    settings = get_settings()
    result = await db.execute(
        select(GeneratedCreative)
        .options(selectinload(GeneratedCreative.assets))
        .where(GeneratedCreative.id == creative_id, GeneratedCreative.organization_id == org_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Creative not found")

    out = CreativeOut.model_validate(c)
    out.assets = [_build_asset_out(a, settings) for a in c.assets]
    return out


@router.post("/{creative_id}/quality-check")
async def run_quality_check(
    creative_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = get_settings()
    result = await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == creative_id, GeneratedCreative.organization_id == org_id
        )
    )
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    pv_result = await db.execute(
        select(PromptVersion).where(PromptVersion.id == creative.prompt_version_id)
    )
    pv = pv_result.scalar_one_or_none()

    from packages.quality_engine.engine import QualityEngine

    # Load image data from storage
    img_data: bytes | None = None
    if creative.storage_key and creative.storage_backend == "local":
        from packages.storage.local import LocalStorage

        ls = LocalStorage(base_dir=settings.storage_local_dir, secret_key=settings.secret_key)
        try:
            img_data = await ls.get(str(org_id), creative.storage_key)
        except Exception:
            pass
    elif creative.file_path:
        import pathlib

        p = pathlib.Path(creative.file_path)
        if p.exists():
            img_data = p.read_bytes()

    qe = QualityEngine(cv_enabled=settings.quality_cv_enabled)
    q_result = qe.check(
        data=img_data,
        file_path=creative.file_path or "",
        width=creative.width,
        height=creative.height,
        prompt_text=pv.prompt_text if pv else None,
    )

    qc = QualityCheck(
        organization_id=org_id,
        creative_id=creative.id,
        result=q_result.result,
        findings={"findings": [f.model_dump() for f in q_result.findings]},
    )
    db.add(qc)
    await db.commit()

    return {"result": q_result.result, "findings": [f.model_dump() for f in q_result.findings]}


@router.post("/{creative_id}/policy-check")
async def run_policy_check(
    creative_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    result = await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == creative_id, GeneratedCreative.organization_id == org_id
        )
    )
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    pv_result = await db.execute(
        select(PromptVersion).where(PromptVersion.id == creative.prompt_version_id)
    )
    pv = pv_result.scalar_one_or_none()

    from packages.policy_engine.engine import PolicyEngine

    pe = PolicyEngine()
    p_result = pe.check(text=(pv.prompt_text or "") if pv else "")

    pc = PolicyCheck(
        organization_id=org_id,
        creative_id=creative.id,
        result=p_result.result,
        findings={"findings": [f.model_dump() for f in p_result.findings]},
        rule_set_version=p_result.rule_set_version,
    )
    db.add(pc)
    await db.commit()

    return {
        "result": p_result.result,
        "findings": [f.model_dump() for f in p_result.findings],
        "internal_notice": p_result.internal_notice,
    }


@router.post("/{creative_id}/approve")
async def approve_creative(
    creative_id: uuid.UUID,
    body: ApproveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    settings = get_settings()
    result = await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == creative_id, GeneratedCreative.organization_id == org_id
        )
    )
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner/admin can approve creatives.")

    # Collect un-overridden BLOCKED checks
    blocked_q = await db.execute(
        select(QualityCheck).where(
            QualityCheck.creative_id == creative_id,
            QualityCheck.result == "BLOCKED",
            QualityCheck.override_by.is_(None),
        )
    )
    blocked_p = await db.execute(
        select(PolicyCheck).where(
            PolicyCheck.creative_id == creative_id,
            PolicyCheck.result == "BLOCKED",
            PolicyCheck.override_by.is_(None),
        )
    )
    blocked_checks_q = blocked_q.scalars().all()
    blocked_checks_p = blocked_p.scalars().all()
    has_blocked = bool(blocked_checks_q or blocked_checks_p)

    overridden_ids: list[str] = []

    if has_blocked:
        if not settings.allow_blocked_override:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Creative has BLOCKED checks. Override is disabled (ALLOW_BLOCKED_OVERRIDE=false).",
            )
        if not body.override_blocked:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Creative has BLOCKED checks. Set override_blocked=true and provide a comment.",
            )
        if current_user.role != "owner":
            raise HTTPException(
                status_code=403,
                detail="Only 'owner' role can override BLOCKED checks.",
            )
        if not body.comment:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A comment is required when overriding BLOCKED checks.",
            )
        # Record overrides
        for qc in blocked_checks_q:
            qc.override_by = current_user.id
            qc.override_reason = body.comment
            overridden_ids.append(str(qc.id))
        for pc in blocked_checks_p:
            pc.override_by = current_user.id
            pc.override_reason = body.comment
            overridden_ids.append(str(pc.id))

    pv_result = await db.execute(
        select(PromptVersion).where(PromptVersion.id == creative.prompt_version_id)
    )
    pv = pv_result.scalar_one_or_none()

    approval = Approval(
        organization_id=org_id,
        creative_id=creative.id,
        action="approve",
        decision="approved",
        decided_by=current_user.id,
        comment=body.comment,
        snapshot_prompt=pv.prompt_text if pv else None,
        overridden_check_ids={"ids": overridden_ids} if overridden_ids else None,
    )
    db.add(approval)
    creative.status = "approved"

    audit = AuditLog(
        organization_id=org_id,
        actor_id=current_user.id,
        action="approve_creative",
        entity_type="generated_creative",
        entity_id=str(creative_id),
        payload={"override_blocked": body.override_blocked, "overridden_ids": overridden_ids},
        result="success",
        dry_run=False,
    )
    db.add(audit)
    await db.commit()
    return {"status": "approved", "creative_id": str(creative_id)}


@router.post("/{creative_id}/reject")
async def reject_creative(
    creative_id: uuid.UUID,
    body: RejectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner/admin can reject creatives.")

    result = await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == creative_id, GeneratedCreative.organization_id == org_id
        )
    )
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    approval = Approval(
        organization_id=org_id,
        creative_id=creative.id,
        action="reject",
        decision="rejected",
        decided_by=current_user.id,
        comment=body.comment,
    )
    db.add(approval)
    creative.status = "rejected"

    audit = AuditLog(
        organization_id=org_id,
        actor_id=current_user.id,
        action="reject_creative",
        entity_type="generated_creative",
        entity_id=str(creative_id),
        result="success",
        dry_run=False,
    )
    db.add(audit)
    await db.commit()
    return {"status": "rejected", "creative_id": str(creative_id)}


@router.post("/{creative_id}/request-variation")
async def request_variation(
    creative_id: uuid.UUID,
    body: RequestVariationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Reject current creative and enqueue a new variation with the same (or updated) prompt."""
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner/admin can request variations.")

    result = await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == creative_id, GeneratedCreative.organization_id == org_id
        )
    )
    creative = result.scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    # Resolve which prompt version to use for the new variation
    new_pv_id = body.prompt_version_id or creative.prompt_version_id

    # Record the variation request on the current creative
    approval = Approval(
        organization_id=org_id,
        creative_id=creative.id,
        action="request_variation",
        decision="rejected",
        decided_by=current_user.id,
        comment=body.comment,
    )
    db.add(approval)
    creative.status = "rejected"

    # Create new creative stub (caller must trigger generation separately or it goes through service)
    new_creative = GeneratedCreative(
        organization_id=org_id,
        prompt_version_id=new_pv_id,
        provider="pending",
        variation_of_id=creative.id,
        source_ad_id=creative.source_ad_id,
        is_fictitious=creative.is_fictitious,
        status="queued",
    )
    db.add(new_creative)

    audit = AuditLog(
        organization_id=org_id,
        actor_id=current_user.id,
        action="request_variation",
        entity_type="generated_creative",
        entity_id=str(creative_id),
        payload={"new_prompt_version_id": str(new_pv_id)},
        result="success",
        dry_run=False,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(new_creative)

    return {
        "status": "variation_queued",
        "original_creative_id": str(creative_id),
        "new_creative_id": str(new_creative.id),
        "message": "Rejected current creative. New variation is queued — trigger generation to produce the image.",
    }
