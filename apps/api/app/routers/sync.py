from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_org, require_roles
from app.models.meta_sync import MetaSyncRun
from app.models.user import User

router = APIRouter()


class SyncHistoryRequest(BaseModel):
    account_id: str | None = None
    date_start: str | None = None
    date_stop: str | None = None


class SyncIncrementalRequest(BaseModel):
    account_id: str | None = None
    days_back: int = 30


class SyncRunOut(BaseModel):
    id: uuid.UUID
    account_external_id: str
    kind: str
    status: str
    started_at: Any
    finished_at: Any
    date_start: str | None
    date_stop: str | None
    campaigns_created: int
    campaigns_updated: int
    adsets_created: int
    adsets_updated: int
    ads_created: int
    ads_updated: int
    snapshots_created: int
    snapshots_updated: int
    assets_created: int
    error_detail: str | None

    model_config = {"from_attributes": True}


@router.post("/meta/history")
async def sync_history(
    body: SyncHistoryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _admin: Annotated[User, Depends(require_roles("owner", "admin"))],
) -> dict[str, Any]:
    settings = get_settings()
    account_id = body.account_id or settings.meta_ad_account_id
    if account_id.startswith("PREENCHER_"):
        raise HTTPException(
            status_code=422,
            detail="META_AD_ACCOUNT_ID not configured. Set it in .env or pass account_id.",
        )
    today = date.today().isoformat()
    date_start = body.date_start or settings.meta_sync_history_date_start
    date_stop = body.date_stop or today

    run = await _run_sync(db, org_id, account_id, date_start, date_stop, "history", settings)
    return {
        "sync_run_id": str(run.id),
        "status": run.status,
        "message": f"History sync {run.status}. Ads: {run.ads_created}c/{run.ads_updated}u, "
                   f"Snapshots: {run.snapshots_created}c/{run.snapshots_updated}u",
    }


@router.post("/meta/incremental")
async def sync_incremental(
    body: SyncIncrementalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    _admin: Annotated[User, Depends(require_roles("owner", "admin"))],
) -> dict[str, Any]:
    settings = get_settings()
    account_id = body.account_id or settings.meta_ad_account_id
    if account_id.startswith("PREENCHER_"):
        raise HTTPException(
            status_code=422,
            detail="META_AD_ACCOUNT_ID not configured.",
        )
    days = max(1, min(body.days_back, 90))
    today = date.today()
    date_start = (today - timedelta(days=days)).isoformat()
    date_stop = today.isoformat()

    run = await _run_sync(db, org_id, account_id, date_start, date_stop, "incremental", settings)
    return {
        "sync_run_id": str(run.id),
        "status": run.status,
        "message": f"Incremental sync {run.status}. Ads: {run.ads_created}c/{run.ads_updated}u, "
                   f"Snapshots: {run.snapshots_created}c/{run.snapshots_updated}u",
    }


@router.get("/meta/runs")
async def list_sync_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    limit: int = 20,
) -> list[SyncRunOut]:
    result = await db.execute(
        select(MetaSyncRun)
        .where(MetaSyncRun.organization_id == org_id)
        .order_by(MetaSyncRun.created_at.desc())
        .limit(min(limit, 100))
    )
    return [SyncRunOut.model_validate(r) for r in result.scalars().all()]


@router.get("/meta/runs/{run_id}")
async def get_sync_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
) -> SyncRunOut:
    result = await db.execute(
        select(MetaSyncRun).where(
            MetaSyncRun.id == run_id,
            MetaSyncRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Sync run not found")
    return SyncRunOut.model_validate(run)


# ── Internal helper ──────────────────────────────────────────────

async def _run_sync(
    db: AsyncSession,
    org_id: uuid.UUID,
    account_id: str,
    date_start: str,
    date_stop: str,
    kind: str,
    settings: Any,
) -> MetaSyncRun:
    from packages.meta_client.factory import get_meta_client

    from app.services.meta_import import MetaImportService

    client = get_meta_client(settings.meta_provider)
    is_mock = settings.meta_provider == "mock"

    service = MetaImportService(
        client=client,
        db=db,
        org_id=org_id,
        account_external_id=account_id,
        source_label="mock" if is_mock else "real",
        is_fictitious=is_mock,
    )
    return await service.run(kind=kind, date_start=date_start, date_stop=date_stop)
