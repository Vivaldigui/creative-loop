from __future__ import annotations

"""
Celery tasks for Meta read-only import (Phase 2).
Tasks run synchronously via asyncio.run() since Celery workers use threads.
All tasks are read-only: no write calls to Meta.
"""

import asyncio
from datetime import date, timedelta

import structlog

from app.worker.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="tasks.sync_meta_history", bind=True, max_retries=2)
def sync_meta_history_task(
    self,
    org_id: str,
    account_id: str,
    date_start: str,
    date_stop: str,
    sync_run_id: str | None = None,
) -> dict:
    """Import full historical data from Meta for one ad account."""
    try:
        result = asyncio.run(_run_import(org_id, account_id, date_start, date_stop, "history"))
        return result
    except Exception as exc:
        logger.error("sync_meta_history_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="tasks.sync_meta_incremental", bind=True, max_retries=3)
def sync_meta_incremental_task(
    self,
    org_id: str,
    account_id: str,
    days_back: int = 30,
) -> dict:
    """Import last N days of Meta data for one ad account."""
    today = date.today()
    date_start = (today - timedelta(days=days_back)).isoformat()
    date_stop = today.isoformat()
    try:
        result = asyncio.run(_run_import(org_id, account_id, date_start, date_stop, "incremental"))
        return result
    except Exception as exc:
        logger.error("sync_meta_incremental_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="tasks.dispatch_meta_incremental_syncs")
def dispatch_meta_incremental_syncs() -> dict:
    """
    Beat task: dispatches incremental sync for all orgs with META_PROVIDER=real.
    For single-tenant MVP, uses env settings directly.
    Multi-tenant dispatch (querying IntegrationCredential per org) is Phase 3+.
    """
    from app.config import get_settings
    s = get_settings()
    if s.meta_provider != "real":
        logger.info("dispatch_incremental_skipped", reason="meta_provider != real")
        return {"skipped": True}
    if s.meta_ad_account_id.startswith("PREENCHER_"):
        logger.info("dispatch_incremental_skipped", reason="account_id not configured")
        return {"skipped": True}

    task = sync_meta_incremental_task.delay(
        org_id="env",  # sentinel: task resolves org from DB by account_id
        account_id=s.meta_ad_account_id,
        days_back=s.meta_sync_incremental_days,
    )
    return {"dispatched": True, "task_id": task.id}


# ── Async runner ──────────────────────────────────────────────────

async def _run_import(
    org_id: str,
    account_id: str,
    date_start: str,
    date_stop: str,
    kind: str,
) -> dict:
    from packages.meta_client.factory import get_meta_client

    from app.config import get_settings
    from app.db import get_session_factory
    from app.services.meta_import import MetaImportService

    s = get_settings()
    client = get_meta_client(s.meta_provider)
    is_mock = s.meta_provider == "mock"

    session_factory = get_session_factory()
    async with session_factory() as db:
        # Resolve org_id: if sentinel "env", find by account_id or use first org
        resolved_org = await _resolve_org(db, org_id, account_id)

        service = MetaImportService(
            client=client,
            db=db,
            org_id=resolved_org,
            account_external_id=account_id,
            source_label="mock" if is_mock else "real",
            is_fictitious=is_mock,
        )
        run = await service.run(kind=kind, date_start=date_start, date_stop=date_stop)

    return {
        "run_id": str(run.id),
        "status": run.status,
        "kind": kind,
        "ads_created": run.ads_created,
        "ads_updated": run.ads_updated,
        "snapshots_created": run.snapshots_created,
        "snapshots_updated": run.snapshots_updated,
    }


async def _resolve_org(db, org_id: str, account_id: str):
    """Resolve org UUID from string parameter or from first available org."""
    import uuid as _uuid

    from sqlalchemy import select

    from app.models.user import Organization

    if org_id and org_id != "env":
        try:
            return _uuid.UUID(org_id)
        except ValueError:
            pass

    # Fall back: first org in DB
    result = await db.execute(select(Organization).limit(1))
    org = result.scalar_one_or_none()
    if not org:
        raise ValueError("No organisation found in database.")
    return org.id
