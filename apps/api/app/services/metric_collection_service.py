"""
MetricCollectionService — collects Meta metrics for published experiment variants.

Uses the same MetricNormalizer + iter_insights pattern as Phase 2.
Idempotent: upserts via UniqueConstraint on (variant_id, date_start, date_stop, level, breakdown_key, attribution_window).
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.experiment import Experiment, ExperimentVariant
from app.models.publish import PublishedAd
from app.models.variant_metric import VariantPerformanceSnapshot

logger = structlog.get_logger()


class MetricCollectionService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def collect_for_experiment(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
        days_back: int = 30,
    ) -> dict[str, Any]:
        """
        Collect metrics for all variants of an experiment.
        Returns a summary dict.
        """
        result = await db.execute(
            select(Experiment)
            .where(Experiment.id == experiment_id, Experiment.organization_id == org_id)
        )
        exp = result.scalar_one_or_none()
        if not exp:
            return {"error": "experiment_not_found"}

        if exp.status not in ("running", "evaluating"):
            return {"skipped": True, "reason": f"experiment_status={exp.status}"}

        # Load variants with published_ad_id
        var_result = await db.execute(
            select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == experiment_id,
                ExperimentVariant.organization_id == org_id,
                ExperimentVariant.published_ad_id.isnot(None),
            )
        )
        variants = var_result.scalars().all()

        if not variants:
            return {"skipped": True, "reason": "no_variants_with_published_ads"}

        today = date.today()
        date_start = (today - timedelta(days=days_back)).isoformat()
        date_stop = today.isoformat()

        total_created = 0
        total_updated = 0

        for variant in variants:
            created, updated = await self._collect_variant(
                db=db,
                org_id=org_id,
                experiment_id=experiment_id,
                variant=variant,
                date_start=date_start,
                date_stop=date_stop,
            )
            total_created += created
            total_updated += updated

        # Update maturation flags
        maturation_days = self._settings.exp_default_maturation_window_days
        if exp.min_criteria:
            maturation_days = exp.min_criteria.get("maturation_window_days", maturation_days)

        await self._update_maturation(db, org_id, experiment_id, maturation_days)
        await db.commit()

        return {
            "experiment_id": str(experiment_id),
            "snapshots_created": total_created,
            "snapshots_updated": total_updated,
            "date_start": date_start,
            "date_stop": date_stop,
        }

    async def _collect_variant(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
        variant: ExperimentVariant,
        date_start: str,
        date_stop: str,
    ) -> tuple[int, int]:
        """Collect and upsert metrics for one variant. Returns (created, updated)."""
        # Get meta_ad_id from published_ad
        pad_result = await db.execute(
            select(PublishedAd).where(PublishedAd.id == variant.published_ad_id)
        )
        pad = pad_result.scalar_one_or_none()
        if not pad or not pad.meta_ad_id:
            return 0, 0

        meta_ad_id = pad.meta_ad_id

        # In mock mode, generate fictitious data
        if self._settings.meta_provider == "mock":
            return await self._upsert_mock_snapshot(
                db, org_id, experiment_id, variant, pad, meta_ad_id, date_start, date_stop
            )

        # Real mode: call Meta API
        return await self._collect_real(
            db, org_id, experiment_id, variant, pad, meta_ad_id, date_start, date_stop
        )

    async def _upsert_mock_snapshot(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
        variant: ExperimentVariant,
        pad: PublishedAd,
        meta_ad_id: str,
        date_start: str,
        date_stop: str,
    ) -> tuple[int, int]:
        """Insert a mock snapshot for development/testing."""
        import hashlib
        import random
        # Deterministic seed based on variant + date
        seed_str = f"{variant.id}{date_start}"
        seed = int(hashlib.sha256(seed_str.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        impressions = rng.randint(500, 5000)
        clicks = rng.randint(10, int(impressions * 0.05))
        spend = round(rng.uniform(10.0, 200.0), 2)
        purchases = rng.randint(0, max(0, clicks // 10))

        existing = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.variant_id == variant.id,
                VariantPerformanceSnapshot.date_start == date_start,
                VariantPerformanceSnapshot.date_stop == date_stop,
                VariantPerformanceSnapshot.level == "ad",
                VariantPerformanceSnapshot.breakdown_key.is_(None),
                VariantPerformanceSnapshot.attribution_window.is_(None),
            ).limit(1)
        )
        ex_snap = existing.scalar_one_or_none()

        if ex_snap:
            ex_snap.impressions = impressions
            ex_snap.clicks = clicks
            ex_snap.spend = spend
            ex_snap.purchases = purchases
            ex_snap.ctr = (clicks / impressions * 100) if impressions else None
            ex_snap.cpc = (spend / clicks) if clicks else None
            return 0, 1

        snap = VariantPerformanceSnapshot(
            organization_id=org_id,
            experiment_id=experiment_id,
            variant_id=variant.id,
            published_ad_id=pad.id,
            meta_ad_id=meta_ad_id,
            date_start=date_start,
            date_stop=date_stop,
            level="ad",
            impressions=impressions,
            clicks=clicks,
            spend=spend,
            purchases=purchases,
            ctr=(clicks / impressions * 100) if impressions else None,
            cpc=(spend / clicks) if clicks else None,
            cpm=(spend / impressions * 1000) if impressions else None,
            is_matured=False,
            is_fictitious=True,
        )
        db.add(snap)
        return 1, 0

    async def _collect_real(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
        variant: ExperimentVariant,
        pad: PublishedAd,
        meta_ad_id: str,
        date_start: str,
        date_stop: str,
    ) -> tuple[int, int]:
        """Collect from real Meta API using iter_insights."""
        from packages.meta_client.factory import get_meta_client
        from packages.meta_client.normalize import MetricNormalizer

        client = get_meta_client(self._settings.meta_provider)
        normalizer = MetricNormalizer()
        created = updated = 0

        async for insight_page in client.iter_insights(
            account_id=self._settings.meta_ad_account_id,
            ad_ids=[meta_ad_id],
            date_start=date_start,
            date_stop=date_stop,
        ):
            for raw in insight_page:
                normalized = normalizer.normalize(raw)
                existing = await db.execute(
                    select(VariantPerformanceSnapshot).where(
                        VariantPerformanceSnapshot.variant_id == variant.id,
                        VariantPerformanceSnapshot.date_start == normalized.get("date_start"),
                        VariantPerformanceSnapshot.date_stop == normalized.get("date_stop"),
                        VariantPerformanceSnapshot.level == "ad",
                        VariantPerformanceSnapshot.breakdown_key.is_(None),
                        VariantPerformanceSnapshot.attribution_window.is_(None),
                    ).limit(1)
                )
                ex_snap = existing.scalar_one_or_none()
                if ex_snap:
                    for field_name, val in normalized.items():
                        if hasattr(ex_snap, field_name):
                            setattr(ex_snap, field_name, val)
                    updated += 1
                else:
                    snap = VariantPerformanceSnapshot(
                        organization_id=org_id,
                        experiment_id=experiment_id,
                        variant_id=variant.id,
                        published_ad_id=pad.id,
                        meta_ad_id=meta_ad_id,
                        level="ad",
                        is_matured=False,
                        is_fictitious=False,
                        **{k: v for k, v in normalized.items() if hasattr(VariantPerformanceSnapshot, k)},
                    )
                    db.add(snap)
                    created += 1
        return created, updated

    async def _update_maturation(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
        maturation_days: int,
    ) -> None:
        """Mark snapshots as matured when their date_stop is old enough."""
        from datetime import date as _date
        cutoff = (_date.today() - timedelta(days=maturation_days)).isoformat()

        snap_result = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.experiment_id == experiment_id,
                VariantPerformanceSnapshot.organization_id == org_id,
                VariantPerformanceSnapshot.is_matured == False,  # noqa: E712
            )
        )
        for snap in snap_result.scalars().all():
            if snap.date_stop and snap.date_stop <= cutoff:
                snap.is_matured = True
