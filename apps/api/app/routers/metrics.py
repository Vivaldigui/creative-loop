from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_org, get_current_user
from app.models.audit import AuditLog
from app.models.source_ad import PerformanceSnapshot, SourceAd
from app.models.user import User

router = APIRouter()


@router.get("")
async def get_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    date_start: str | None = Query(default=None),
    date_stop: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> dict:
    q = select(
        func.sum(PerformanceSnapshot.spend).label("total_spend"),
        func.sum(PerformanceSnapshot.impressions).label("total_impressions"),
        func.sum(PerformanceSnapshot.clicks).label("total_clicks"),
        func.sum(PerformanceSnapshot.purchases).label("total_purchases"),
        func.sum(PerformanceSnapshot.leads).label("total_leads"),
        func.sum(PerformanceSnapshot.adds_to_cart).label("total_adds_to_cart"),
        func.sum(PerformanceSnapshot.purchase_value).label("total_purchase_value"),
        func.avg(PerformanceSnapshot.roas).label("avg_roas"),
        func.avg(PerformanceSnapshot.ctr).label("avg_ctr"),
        func.avg(PerformanceSnapshot.cpc).label("avg_cpc"),
        func.avg(PerformanceSnapshot.cpm).label("avg_cpm"),
    ).where(PerformanceSnapshot.organization_id == org_id)

    if date_start:
        q = q.where(PerformanceSnapshot.date_start >= date_start)
    if date_stop:
        q = q.where(PerformanceSnapshot.date_stop <= date_stop)

    # Filter by source (real/mock) via join if requested
    if source is not None:
        q = q.join(SourceAd, SourceAd.id == PerformanceSnapshot.source_ad_id).where(
            SourceAd.source == source
        )

    result = await db.execute(q)
    row = result.one()

    total_spend = float(row.total_spend or 0)
    total_purchase_value = float(row.total_purchase_value or 0)
    total_impressions = int(row.total_impressions or 0)
    derived_roas = round(total_purchase_value / total_spend, 4) if total_spend > 0 else None

    return {
        "total_spend": total_spend,
        "total_impressions": total_impressions,
        "total_clicks": int(row.total_clicks or 0),
        "total_purchases": int(row.total_purchases or 0),
        "total_leads": int(row.total_leads or 0),
        "total_adds_to_cart": int(row.total_adds_to_cart or 0),
        "total_purchase_value": total_purchase_value,
        "avg_roas": float(row.avg_roas or 0),
        "derived_roas": derived_roas,
        "avg_ctr": float(row.avg_ctr or 0),
        "avg_cpc": float(row.avg_cpc or 0),
        "avg_cpm": float(row.avg_cpm or 0),
    }


@router.get("/top-ads")
async def get_top_ads(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    metric: str = Query(default="roas"),
    limit: int = Query(default=10, le=50),
    source: str | None = Query(default=None),
) -> list[dict]:
    allowed = {"roas", "ctr", "purchases", "spend", "leads"}
    if metric not in allowed:
        metric = "roas"

    metric_col = getattr(PerformanceSnapshot, metric, PerformanceSnapshot.roas)
    q = (
        select(SourceAd, func.avg(metric_col).label("metric_value"))
        .join(PerformanceSnapshot, PerformanceSnapshot.source_ad_id == SourceAd.id)
        .where(SourceAd.organization_id == org_id)
        .group_by(SourceAd.id)
        .order_by(func.avg(metric_col).desc().nullslast())
        .limit(limit)
    )
    if source is not None:
        q = q.where(SourceAd.source == source)

    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": str(ad.id),
            "name": ad.name,
            "performance_label": ad.performance_label,
            "source": ad.source,
            "is_fictitious": ad.is_fictitious,
            metric: float(val) if val is not None else None,
        }
        for ad, val in rows
    ]


@router.get("/audit-logs")
async def get_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: Annotated[uuid.UUID, Depends(get_current_org)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
) -> list[dict]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "result": log.result,
            "dry_run": log.dry_run,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
