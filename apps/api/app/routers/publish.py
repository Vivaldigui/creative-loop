"""
Publish router — Phase 6: DRY_RUN simulation + real Meta API publish.

Endpoints:
  POST /publish/meta/validate                     — guard checks; no persistence
  POST /publish/meta/dry-run                      — full DRY_RUN simulation
  POST /publish/meta                              — real Meta publish (guarded)
  POST /publish/meta/drafts                       — create/update publication draft
  GET  /publish/meta/drafts                       — list drafts
  GET  /publication-drafts/{id}                   — draft detail
  GET  /publication-attempts/{id}                 — attempt detail
  GET  /publication-attempts/{id}/status          — real publish status + steps
  GET  /published-ads                             — list published ads
  GET  /published-ads/{id}                        — published ad detail
  POST /published-ads/{id}/refresh-status         — query Meta for current status
  POST /published-ads/{id}/activate               — manually activate a PAUSED ad
  POST /published-ads/{id}/pause                  — pause an active ad
  POST /published-ads/{id}/emergency-pause        — emergency pause (minimal barriers)

Real publish safety: both DRY_RUN=false and META_WRITE_ENABLED=true must be set.
Ads are ALWAYS created PAUSED. Activation is a separate manual action.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, get_current_user, require_roles
from app.models.creative import GeneratedCreative
from app.models.publication import PublicationAttempt, PublicationDraft
from app.models.publish import PublishedAd
from app.models.user import User
from app.schemas.publish import (
    ActivateRequest,
    ActivateResponse,
    AttemptOut,
    CheckResultOut,
    DraftOut,
    DraftUpsertRequest,
    DryRunRequest,
    DryRunResponse,
    PauseResponse,
    PublishedAdOut,
    PublishStatusResponse,
    RealPublishRequest,
    RealPublishResponse,
    StepOut,
    ValidateRequest,
    ValidateResponse,
)
from app.services.publication_service import PublicationService

router = APIRouter()          # mounted at /publish
drafts_router = APIRouter()   # mounted at / (root) for /publication-drafts, /publication-attempts, /published-ads

_EDITOR_ROLES = require_roles("owner", "admin")


def _get_service() -> PublicationService:
    return PublicationService(get_settings())


def _correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-ID") or str(uuid.uuid4())


# ── POST /publish/meta/validate ───────────────────────────────────────────────

@router.post("/meta/validate", response_model=ValidateResponse, tags=["Publish"])
async def validate_publication(
    body: ValidateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(_EDITOR_ROLES)],
) -> Any:
    """
    Validate a creative for publication without creating an attempt.
    Returns guard check results and a payload preview.
    """
    settings = get_settings()

    if not settings.dry_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available in DRY_RUN mode.",
        )

    creative = (await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == body.creative_id,
            GeneratedCreative.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found.")

    svc = _get_service()

    payload = svc.build_payload(
        creative=creative,
        campaign_name=body.campaign_name or f"[DRY_RUN] {creative.id}",
        adset_name=body.adset_name or f"[DRY_RUN] AdSet {creative.id}",
        ad_name=body.ad_name or f"[DRY_RUN] Ad {creative.id}",
        objective=body.objective,
        optimization_goal=body.optimization_goal,
        daily_budget_brl=body.daily_budget_brl,
        landing_url=body.landing_url,
        targeting=body.targeting,
    )

    from packages.meta_client.publish.serialization import serialize_full_payload
    payload_dict = serialize_full_payload(payload)

    checks = await svc.validate(
        db=db,
        creative=creative,
        actor=actor,
        org_id=org_id,
        payload=payload,
        daily_budget_brl=body.daily_budget_brl,
        landing_url=body.landing_url,
        objective=body.objective,
        optimization_goal=body.optimization_goal,
        idempotency_key=body.idempotency_key,
        experiment_id=body.experiment_id,
    )

    blocked = [c for c in checks if not c["passed"] and c["severity"] == "blocked"]
    warnings = [c for c in checks if c["severity"] == "warning"]

    return ValidateResponse(
        creative_id=str(body.creative_id),
        passed=len(blocked) == 0,
        blocked_count=len(blocked),
        warning_count=len(warnings),
        checks=[CheckResultOut(**c) for c in checks],
        payload_preview=payload_dict,
        dry_run_mode=True,
    )


# ── POST /publish/meta/dry-run ────────────────────────────────────────────────

@router.post(
    "/meta/dry-run",
    status_code=status.HTTP_201_CREATED,
    response_model=DryRunResponse,
    tags=["Publish"],
)
async def publish_dry_run(
    body: DryRunRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(_EDITOR_ROLES)],
) -> Any:
    """
    Full DRY_RUN publish simulation.

    Enforces all guards, generates simulated IDs, persists PublicationAttempt
    and AuditLog. Returns 200 (not 201) for idempotent retries with the same
    payload, 409 for same key + different payload.
    """
    settings = get_settings()
    correlation_id = _correlation_id(request)

    if not settings.dry_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available in DRY_RUN mode. Set DRY_RUN=true.",
        )

    creative = (await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == body.creative_id,
            GeneratedCreative.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found.")

    svc = _get_service()

    payload = svc.build_payload(
        creative=creative,
        campaign_name=body.campaign_name or f"[DRY_RUN] Campaign {creative.id}",
        adset_name=body.adset_name or f"[DRY_RUN] AdSet {creative.id}",
        ad_name=body.ad_name or f"[DRY_RUN] Ad {creative.id}",
        objective=body.objective,
        optimization_goal=body.optimization_goal,
        billing_event=body.billing_event,
        bid_strategy=body.bid_strategy,
        daily_budget_brl=body.daily_budget_brl,
        landing_url=body.landing_url,
        tracking_params=body.tracking_params,
        headline=body.headline,
        body_text=body.body_text,
        cta_type=body.cta_type,
        targeting=body.targeting,
        placements=body.placements,
        promoted_object=body.promoted_object,
    )

    result = await svc.dry_run(
        db=db,
        creative=creative,
        actor=actor,
        org_id=org_id,
        payload=payload,
        daily_budget_brl=body.daily_budget_brl,
        landing_url=body.landing_url,
        objective=body.objective,
        optimization_goal=body.optimization_goal,
        idempotency_key=body.idempotency_key,
        correlation_id=correlation_id,
        experiment_id=body.experiment_id,
        draft_id=body.draft_id,
    )

    # 409 for idempotency conflict
    if result.get("result") == "rejected":
        blocked = result.get("blocked", [])
        if any("idempotency_conflict" in b.get("code", "") for b in blocked):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result,
        )

    return DryRunResponse(**result)


# ── POST /publish/meta (real publish — Phase 6) ───────────────────────────────

@router.post(
    "/meta",
    status_code=status.HTTP_201_CREATED,
    response_model=RealPublishResponse,
    tags=["Publish"],
)
async def publish_meta_real(
    body: RealPublishRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(_EDITOR_ROLES)],
) -> Any:
    """
    Real Meta publish.

    Both DRY_RUN=false AND META_WRITE_ENABLED=true must be configured.
    Ad is always created PAUSED — manual activation required.
    confirm_paused=true is mandatory to confirm caller awareness.

    Runs synchronously; for large campaigns consider the async Celery path
    (see tasks.publish_real).
    """
    settings = get_settings()
    correlation_id = _correlation_id(request)

    if settings.dry_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DRY_RUN=true — real publish is blocked. Set DRY_RUN=false to proceed.",
        )
    if not settings.meta_write_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "META_WRITE_ENABLED=false — real publish is blocked. "
                "Both DRY_RUN=false and META_WRITE_ENABLED=true are required."
            ),
        )
    if not body.confirm_paused:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "confirm_paused must be true. "
                "The ad will be created PAUSED and requires manual activation."
            ),
        )

    creative = (await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == body.creative_id,
            GeneratedCreative.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found.")

    svc = _get_service()
    payload = svc.build_payload(
        creative=creative,
        campaign_name=body.campaign_name or f"Campaign [{creative.id}]",
        adset_name=body.adset_name or f"AdSet [{creative.id}]",
        ad_name=body.ad_name or f"Ad [{creative.id}]",
        objective=body.objective,
        optimization_goal=body.optimization_goal,
        billing_event=body.billing_event,
        bid_strategy=body.bid_strategy,
        daily_budget_brl=body.daily_budget_brl,
        landing_url=body.landing_url,
        tracking_params=body.tracking_params,
        headline=body.headline,
        body_text=body.body_text,
        cta_type=body.cta_type,
        targeting=body.targeting,
        placements=body.placements,
        promoted_object=body.promoted_object,
    )

    # Image bytes: real publish requires the image stored on the creative
    image_bytes = b""
    if creative.image_data:
        import base64
        try:
            image_bytes = base64.b64decode(creative.image_data)
        except Exception:
            image_bytes = creative.image_data.encode() if isinstance(creative.image_data, str) else b""

    result = await svc.publish_real(
        db=db,
        creative=creative,
        actor=actor,
        org_id=org_id,
        payload=payload,
        image_bytes=image_bytes,
        daily_budget_brl=body.daily_budget_brl,
        landing_url=body.landing_url,
        objective=body.objective,
        optimization_goal=body.optimization_goal,
        idempotency_key=body.idempotency_key,
        correlation_id=correlation_id,
        credentials_valid=bool(settings.meta_access_token and not settings.meta_access_token.startswith("PREENCHER_")),
        experiment_id=body.experiment_id,
        draft_id=body.draft_id,
    )

    if result.get("result") == "rejected":
        blocked = result.get("blocked", [])
        if any("idempotency_conflict" in b.get("code", "") for b in blocked):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result)

    return RealPublishResponse(**result)


# ── Draft endpoints ───────────────────────────────────────────────────────────

@router.post("/meta/drafts", status_code=status.HTTP_201_CREATED, tags=["Publish"])
async def create_or_update_draft(
    body: DraftUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(_EDITOR_ROLES)],
) -> Any:
    """Create or update a publication draft for a creative."""
    creative = (await db.execute(
        select(GeneratedCreative).where(
            GeneratedCreative.id == body.creative_id,
            GeneratedCreative.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found.")

    draft = PublicationDraft(
        organization_id=org_id,
        creative_id=body.creative_id,
        experiment_id=body.experiment_id,
        campaign_config=body.campaign_config,
        adset_config=body.adset_config,
        ad_config=body.ad_config,
        landing_url=body.landing_url,
        tracking_params=body.tracking_params,
        status="draft",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return {
        "id": str(draft.id),
        "creative_id": str(draft.creative_id),
        "status": draft.status,
        "created_at": draft.created_at.isoformat(),
    }


@router.get("/meta/drafts", tags=["Publish"])
async def list_drafts(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _actor: Annotated[User, Depends(get_current_user)],
    creative_id: uuid.UUID | None = Query(default=None),
    draft_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    q = select(PublicationDraft).where(PublicationDraft.organization_id == org_id)
    if creative_id:
        q = q.where(PublicationDraft.creative_id == creative_id)
    if draft_status:
        q = q.where(PublicationDraft.status == draft_status)
    q = q.order_by(PublicationDraft.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(q)).scalars().all()
    return [
        DraftOut(
            id=str(d.id),
            creative_id=str(d.creative_id),
            experiment_id=str(d.experiment_id) if d.experiment_id else None,
            status=d.status,
            payload_hash=d.payload_hash,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )
        for d in rows
    ]


@drafts_router.get("/publication-drafts/{draft_id}", tags=["Publish"])
async def get_draft(
    draft_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _actor: Annotated[User, Depends(get_current_user)],
) -> Any:
    draft = (await db.execute(
        select(PublicationDraft).where(
            PublicationDraft.id == draft_id,
            PublicationDraft.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found.")

    last_attempt = (await db.execute(
        select(PublicationAttempt).where(
            PublicationAttempt.draft_id == draft_id,
        ).order_by(PublicationAttempt.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    return {
        "id": str(draft.id),
        "creative_id": str(draft.creative_id),
        "experiment_id": str(draft.experiment_id) if draft.experiment_id else None,
        "status": draft.status,
        "campaign_config": draft.campaign_config,
        "adset_config": draft.adset_config,
        "ad_config": draft.ad_config,
        "landing_url": draft.landing_url,
        "tracking_params": draft.tracking_params,
        "payload": draft.payload,
        "payload_hash": draft.payload_hash,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
        "last_attempt": (
            AttemptOut(
                id=str(last_attempt.id),
                creative_id=str(last_attempt.creative_id),
                draft_id=str(last_attempt.draft_id) if last_attempt.draft_id else None,
                idempotency_key=last_attempt.idempotency_key,
                payload_hash=last_attempt.payload_hash,
                mode=last_attempt.mode,
                correlation_id=last_attempt.correlation_id,
                result=last_attempt.result,
                simulated_response=last_attempt.simulated_response,
                checks=last_attempt.checks,
                error_detail=last_attempt.error_detail,
                published_ad_id=str(last_attempt.published_ad_id) if last_attempt.published_ad_id else None,
                created_at=last_attempt.created_at.isoformat(),
            ).model_dump()
            if last_attempt else None
        ),
    }


@drafts_router.get("/publication-attempts/{attempt_id}", tags=["Publish"])
async def get_attempt(
    attempt_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _actor: Annotated[User, Depends(get_current_user)],
) -> Any:
    attempt = (await db.execute(
        select(PublicationAttempt).where(
            PublicationAttempt.id == attempt_id,
            PublicationAttempt.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")

    return AttemptOut(
        id=str(attempt.id),
        creative_id=str(attempt.creative_id),
        draft_id=str(attempt.draft_id) if attempt.draft_id else None,
        idempotency_key=attempt.idempotency_key,
        payload_hash=attempt.payload_hash,
        mode=attempt.mode,
        correlation_id=attempt.correlation_id,
        result=attempt.result,
        simulated_response=attempt.simulated_response,
        checks=attempt.checks,
        error_detail=attempt.error_detail,
        published_ad_id=str(attempt.published_ad_id) if attempt.published_ad_id else None,
        created_at=attempt.created_at.isoformat(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — real publish status, published-ads, activation, pause
# ─────────────────────────────────────────────────────────────────────────────

@drafts_router.get(
    "/publication-attempts/{attempt_id}/status",
    response_model=PublishStatusResponse,
    tags=["Publish"],
)
async def get_attempt_status(
    attempt_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _actor: Annotated[User, Depends(get_current_user)],
) -> Any:
    """Poll status of a real publish attempt including per-step progress."""
    from app.models.publish import PublicationStep

    attempt = (await db.execute(
        select(PublicationAttempt).where(
            PublicationAttempt.id == attempt_id,
            PublicationAttempt.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")

    steps_rows = (await db.execute(
        select(PublicationStep).where(
            PublicationStep.attempt_id == attempt_id,
        ).order_by(PublicationStep.created_at)
    )).scalars().all()

    published_ad: PublishedAd | None = None
    if attempt.published_ad_id:
        published_ad = (await db.execute(
            select(PublishedAd).where(PublishedAd.id == attempt.published_ad_id)
        )).scalar_one_or_none()

    return PublishStatusResponse(
        attempt_id=str(attempt.id),
        published_ad_id=str(attempt.published_ad_id) if attempt.published_ad_id else None,
        mode=attempt.mode,
        result=attempt.result,
        workflow_state=published_ad.workflow_state if published_ad else None,
        meta_ad_id=published_ad.meta_ad_id if published_ad else None,
        meta_campaign_id=published_ad.meta_campaign_id if published_ad else None,
        effective_status=published_ad.effective_status if published_ad else None,
        error_detail=attempt.error_detail,
        requires_manual_review=(published_ad.workflow_state == "requires_manual_review") if published_ad else False,
        created_at=attempt.created_at.isoformat(),
        steps=[
            StepOut(
                state=s.state,
                meta_node_id=s.meta_node_id,
                meta_request_id=s.meta_request_id,
                error_code=s.error_code,
                error_detail=s.error_detail,
                is_recoverable=s.is_recoverable,
                finished_at=s.finished_at.isoformat() if s.finished_at else None,
            )
            for s in steps_rows
        ],
    )


@drafts_router.get("/published-ads", tags=["Publish"])
async def list_published_ads(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _actor: Annotated[User, Depends(get_current_user)],
    creative_id: uuid.UUID | None = Query(default=None),
    dry_run: bool | None = Query(default=None),
    ad_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """List published ads for the organisation."""
    q = select(PublishedAd).where(PublishedAd.organization_id == org_id)
    if creative_id:
        q = q.where(PublishedAd.creative_id == creative_id)
    if dry_run is not None:
        q = q.where(PublishedAd.dry_run == dry_run)
    if ad_status:
        q = q.where(PublishedAd.status == ad_status)
    q = q.order_by(PublishedAd.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(q)).scalars().all()
    return [
        PublishedAdOut(
            id=str(ad.id),
            creative_id=str(ad.creative_id),
            dry_run=ad.dry_run,
            status=ad.status,
            effective_status=ad.effective_status,
            workflow_state=ad.workflow_state,
            meta_ad_id=ad.meta_ad_id,
            meta_campaign_id=ad.meta_campaign_id,
            meta_adset_id=ad.meta_adset_id,
            meta_image_hash=ad.meta_image_hash,
            idempotency_tag=ad.idempotency_tag,
            activated_at=ad.activated_at.isoformat() if ad.activated_at else None,
            paused_at=ad.paused_at.isoformat() if ad.paused_at else None,
            last_status_checked_at=ad.last_status_checked_at.isoformat() if ad.last_status_checked_at else None,
            error_detail=ad.error_detail,
            created_at=ad.created_at.isoformat(),
        )
        for ad in rows
    ]


@drafts_router.get("/published-ads/{ad_id}", tags=["Publish"])
async def get_published_ad(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _actor: Annotated[User, Depends(get_current_user)],
) -> Any:
    ad = (await db.execute(
        select(PublishedAd).where(
            PublishedAd.id == ad_id,
            PublishedAd.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Published ad not found.")
    return PublishedAdOut(
        id=str(ad.id),
        creative_id=str(ad.creative_id),
        dry_run=ad.dry_run,
        status=ad.status,
        effective_status=ad.effective_status,
        workflow_state=ad.workflow_state,
        meta_ad_id=ad.meta_ad_id,
        meta_campaign_id=ad.meta_campaign_id,
        meta_adset_id=ad.meta_adset_id,
        meta_image_hash=ad.meta_image_hash,
        idempotency_tag=ad.idempotency_tag,
        activated_at=ad.activated_at.isoformat() if ad.activated_at else None,
        paused_at=ad.paused_at.isoformat() if ad.paused_at else None,
        last_status_checked_at=ad.last_status_checked_at.isoformat() if ad.last_status_checked_at else None,
        error_detail=ad.error_detail,
        created_at=ad.created_at.isoformat(),
    )


@drafts_router.post(
    "/published-ads/{ad_id}/refresh-status",
    tags=["Publish"],
)
async def refresh_ad_status(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(_EDITOR_ROLES)],
) -> Any:
    """Query Meta for current effective_status and update the record."""
    settings = get_settings()
    if settings.dry_run:
        raise HTTPException(status_code=400, detail="refresh-status not available in DRY_RUN mode.")

    ad = (await db.execute(
        select(PublishedAd).where(
            PublishedAd.id == ad_id,
            PublishedAd.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Published ad not found.")

    svc = _get_service()
    return await svc.refresh_status(db=db, published_ad=ad, actor=actor, org_id=org_id)


@drafts_router.post(
    "/published-ads/{ad_id}/activate",
    response_model=ActivateResponse,
    tags=["Publish"],
)
async def activate_ad(
    ad_id: uuid.UUID,
    body: ActivateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(require_roles("owner"))],
) -> Any:
    """
    Manually activate a PAUSED ad.

    Requires role 'owner'. confirmation must equal the ad's meta_ad_id.
    This is a non-idempotent operation — one request only.
    """
    settings = get_settings()
    if settings.dry_run:
        raise HTTPException(status_code=400, detail="Activation not available in DRY_RUN mode.")

    ad = (await db.execute(
        select(PublishedAd).where(
            PublishedAd.id == ad_id,
            PublishedAd.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Published ad not found.")

    svc = _get_service()
    result = await svc.activate(
        db=db, published_ad=ad, actor=actor, org_id=org_id, confirmation=body.confirmation
    )

    if result.get("blocked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result)

    if "error" in result and not result.get("blocked"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result)

    return ActivateResponse(**result)


@drafts_router.post(
    "/published-ads/{ad_id}/pause",
    response_model=PauseResponse,
    tags=["Publish"],
)
async def pause_ad(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(_EDITOR_ROLES)],
) -> Any:
    """Pause an active ad. Requires role 'owner' or 'admin'."""
    settings = get_settings()
    if settings.dry_run:
        raise HTTPException(status_code=400, detail="Pause not available in DRY_RUN mode.")

    ad = (await db.execute(
        select(PublishedAd).where(
            PublishedAd.id == ad_id,
            PublishedAd.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Published ad not found.")

    svc = _get_service()
    result = await svc.pause(db=db, published_ad=ad, actor=actor, org_id=org_id, emergency=False)
    if result.get("blocked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result)
    return PauseResponse(**result)


@drafts_router.post(
    "/published-ads/{ad_id}/emergency-pause",
    response_model=PauseResponse,
    tags=["Publish"],
)
async def emergency_pause_ad(
    ad_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    actor: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Emergency pause — minimal barriers, highest priority.

    Available to any authenticated user (not just owner/admin).
    AuditLog records emergency=True.
    """
    settings = get_settings()
    if settings.dry_run:
        raise HTTPException(status_code=400, detail="Emergency pause not available in DRY_RUN mode.")

    ad = (await db.execute(
        select(PublishedAd).where(
            PublishedAd.id == ad_id,
            PublishedAd.organization_id == org_id,
        )
    )).scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Published ad not found.")
    if not ad.meta_ad_id:
        raise HTTPException(status_code=400, detail="Ad has no meta_ad_id to pause.")

    svc = _get_service()
    result = await svc.pause(db=db, published_ad=ad, actor=actor, org_id=org_id, emergency=True)
    return PauseResponse(**result)
