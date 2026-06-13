"""
Meta read-only import service.

Orchestrates the full import flow:
  account → campaigns → adsets → ads (+ creatives) → images → insights → snapshots

Uses MetaSyncRun as the idempotency/audit record for each execution.
All upserts are keyed on (organization_id, external_id) for entities
and on (source_ad_id, date_start, date_stop, level, breakdown_key) for snapshots.

WRITE SAFETY: this service only calls iter_* read methods on the client.
publish_dry_run is never called here.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from packages.meta_client.normalize import NORMALIZATION_VERSION, MetricNormalizer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_sync import (
    AdAccount,
    MetaSyncRun,
    SourceAdSet,
    SourceAsset,
    SourceCampaign,
    SourceCreative,
)
from app.models.source_ad import PerformanceSnapshot, SourceAd

logger = structlog.get_logger()
_normalizer = MetricNormalizer()


class MetaImportService:
    """
    Executes a full or incremental Meta import for one ad account.
    Call run() and await it; it returns the MetaSyncRun record.
    """

    def __init__(
        self,
        client: Any,
        db: AsyncSession,
        org_id: uuid.UUID,
        account_external_id: str,
        source_label: str = "real",
        is_fictitious: bool = False,
    ) -> None:
        self._client = client
        self._db = db
        self._org_id = org_id
        self._account_external_id = account_external_id
        self._source = source_label
        self._fictitious = is_fictitious
        self._run: MetaSyncRun | None = None
        self._campaign_map: dict[str, uuid.UUID] = {}   # external_id → internal UUID
        self._adset_map: dict[str, uuid.UUID] = {}
        self._ad_map: dict[str, uuid.UUID] = {}
        self._creative_map: dict[str, uuid.UUID] = {}

    # ── Entry points ─────────────────────────────────────────────

    async def run(
        self,
        kind: str,
        date_start: str,
        date_stop: str,
    ) -> MetaSyncRun:
        """Run a history or incremental import. Returns the MetaSyncRun record."""
        run = await self._create_run(kind, date_start, date_stop)
        self._run = run
        log = logger.bind(
            org_id=str(self._org_id),
            account=self._account_external_id,
            kind=kind,
        )
        log.info("meta_import_started")
        try:
            await self._import_account()
            await self._import_campaigns()
            await self._import_adsets()
            await self._import_ads()
            await self._import_images()
            await self._import_insights(date_start, date_stop)
            run = await self._complete_run(run, "success")
            log.info("meta_import_complete", **_run_summary(run))
        except Exception as exc:
            log.error("meta_import_failed", error=str(exc))
            run = await self._fail_run(run, str(exc))
        return run

    # ── Account ──────────────────────────────────────────────────

    async def _import_account(self) -> None:
        accounts = await self._client.list_ad_accounts()
        for raw in accounts:
            ext_id = raw.get("id", "")
            if not ext_id or (
                ext_id != self._account_external_id
                and f"act_{ext_id}" != self._account_external_id
                and ext_id != f"act_{self._account_external_id}"
            ):
                continue
            business = raw.get("business") or {}
            await self._upsert_account(
                external_id=ext_id,
                name=raw.get("name"),
                currency=raw.get("currency"),
                timezone_name=raw.get("timezone_name"),
                account_status=raw.get("account_status"),
                business_id=business.get("id"),
                raw=_redact_raw(raw),
            )

    async def _upsert_account(self, **kwargs: Any) -> AdAccount:
        ext_id = kwargs["external_id"]
        result = await self._db.execute(
            select(AdAccount).where(
                AdAccount.organization_id == self._org_id,
                AdAccount.external_id == ext_id,
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = AdAccount(
                organization_id=self._org_id,
                external_id=ext_id,
                source=self._source,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)
        obj.name = kwargs.get("name")
        obj.currency = kwargs.get("currency")
        obj.timezone_name = kwargs.get("timezone_name")
        obj.account_status = kwargs.get("account_status")
        obj.business_id = kwargs.get("business_id")
        obj.raw_response = kwargs.get("raw")
        obj.last_synced_at = datetime.now(UTC)
        await self._db.flush()
        return obj

    # ── Campaigns ────────────────────────────────────────────────

    async def _import_campaigns(self) -> None:
        async for raw in self._client.iter_campaigns(self._account_external_id):
            ext_id = raw.get("id", "")
            if not ext_id:
                continue
            obj = await self._upsert_campaign(raw)
            self._campaign_map[ext_id] = obj.id

    async def _upsert_campaign(self, raw: dict[str, Any]) -> SourceCampaign:
        ext_id = raw["id"]
        result = await self._db.execute(
            select(SourceCampaign).where(
                SourceCampaign.organization_id == self._org_id,
                SourceCampaign.external_id == ext_id,
            )
        )
        obj = result.scalar_one_or_none()
        created = obj is None
        if obj is None:
            obj = SourceCampaign(
                organization_id=self._org_id,
                external_id=ext_id,
                source=self._source,
                is_fictitious=self._fictitious,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)
        obj.name = raw.get("name") or ext_id
        obj.objective = raw.get("objective")
        obj.effective_status = raw.get("effective_status")
        obj.configured_status = raw.get("configured_status")
        obj.buying_type = raw.get("buying_type")
        obj.daily_budget = _budget(raw.get("daily_budget"))
        obj.lifetime_budget = _budget(raw.get("lifetime_budget"))
        obj.raw_response = _redact_raw(raw)
        obj.sync_run_id = self._run.id if self._run else None
        await self._db.flush()
        if self._run:
            if created:
                self._run.campaigns_created += 1
            else:
                self._run.campaigns_updated += 1
        return obj

    # ── Ad sets ──────────────────────────────────────────────────

    async def _import_adsets(self) -> None:
        async for raw in self._client.iter_adsets(self._account_external_id):
            ext_id = raw.get("id", "")
            if not ext_id:
                continue
            obj = await self._upsert_adset(raw)
            self._adset_map[ext_id] = obj.id

    async def _upsert_adset(self, raw: dict[str, Any]) -> SourceAdSet:
        ext_id = raw["id"]
        result = await self._db.execute(
            select(SourceAdSet).where(
                SourceAdSet.organization_id == self._org_id,
                SourceAdSet.external_id == ext_id,
            )
        )
        obj = result.scalar_one_or_none()
        created = obj is None
        if obj is None:
            obj = SourceAdSet(
                organization_id=self._org_id,
                external_id=ext_id,
                source=self._source,
                is_fictitious=self._fictitious,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)
        campaign_ext = raw.get("campaign_id")
        obj.campaign_id = self._campaign_map.get(campaign_ext) if campaign_ext else None
        obj.name = raw.get("name") or ext_id
        obj.optimization_goal = raw.get("optimization_goal")
        obj.billing_event = raw.get("billing_event")
        obj.bid_strategy = raw.get("bid_strategy")
        obj.targeting_summary = raw.get("targeting")
        obj.daily_budget = _budget(raw.get("daily_budget"))
        obj.lifetime_budget = _budget(raw.get("lifetime_budget"))
        obj.effective_status = raw.get("effective_status")
        obj.raw_response = _redact_raw(raw)
        obj.sync_run_id = self._run.id if self._run else None
        await self._db.flush()
        if self._run:
            if created:
                self._run.adsets_created += 1
            else:
                self._run.adsets_updated += 1
        return obj

    # ── Ads + Creatives ──────────────────────────────────────────

    async def _import_ads(self) -> None:
        async for raw in self._client.iter_ads(self._account_external_id):
            ext_id = raw.get("id", "")
            if not ext_id:
                continue
            # Upsert creative first (embedded in ad response)
            creative_raw = raw.get("creative") or {}
            creative_obj: SourceCreative | None = None
            if creative_raw.get("id"):
                creative_obj = await self._upsert_creative(creative_raw)
                self._creative_map[creative_raw["id"]] = creative_obj.id

            obj = await self._upsert_ad(raw, creative_obj)
            self._ad_map[ext_id] = obj.id

    async def _upsert_creative(self, raw: dict[str, Any]) -> SourceCreative:
        ext_id = raw["id"]
        result = await self._db.execute(
            select(SourceCreative).where(
                SourceCreative.organization_id == self._org_id,
                SourceCreative.external_id == ext_id,
            )
        )
        obj = result.scalar_one_or_none()
        created = obj is None
        if obj is None:
            obj = SourceCreative(
                organization_id=self._org_id,
                external_id=ext_id,
                source=self._source,
                is_fictitious=self._fictitious,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)
        obj.name = raw.get("name")
        obj.title = raw.get("title")
        obj.body = raw.get("body")
        obj.cta_type = raw.get("call_to_action_type")
        obj.link_url = raw.get("link_url")
        obj.image_hash = raw.get("image_hash")
        obj.image_url = raw.get("image_url")
        obj.thumbnail_url = raw.get("thumbnail_url")
        obj.object_story_spec = raw.get("object_story_spec")
        obj.raw_response = _redact_raw(raw)
        obj.sync_run_id = self._run.id if self._run else None
        await self._db.flush()
        if self._run:
            if created:
                self._run.creatives_created += 1
            else:
                self._run.creatives_updated += 1
        return obj

    async def _upsert_ad(
        self, raw: dict[str, Any], creative: SourceCreative | None
    ) -> SourceAd:
        ext_id = raw["id"]
        result = await self._db.execute(
            select(SourceAd).where(
                SourceAd.organization_id == self._org_id,
                SourceAd.external_id == ext_id,
            )
        )
        obj = result.scalar_one_or_none()
        created = obj is None
        if obj is None:
            obj = SourceAd(
                organization_id=self._org_id,
                external_id=ext_id,
                source=self._source,
                is_fictitious=self._fictitious,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)

        creative_raw = raw.get("creative") or {}
        obj.name = raw.get("name") or ext_id
        obj.headline = creative_raw.get("title")
        obj.body_text = creative_raw.get("body")
        obj.cta = creative_raw.get("call_to_action_type")
        obj.landing_page_url = creative_raw.get("link_url")
        obj.image_url = creative_raw.get("image_url")

        adset_ext = raw.get("adset_id")
        obj.source_adset_id = self._adset_map.get(adset_ext) if adset_ext else None
        obj.source_creative_id = creative.id if creative else None
        obj.effective_status = raw.get("effective_status")
        obj.configured_status = raw.get("configured_status")
        obj.status = (raw.get("effective_status") or "active").lower()
        obj.last_synced_at = datetime.now(UTC)
        obj.sync_run_id = self._run.id if self._run else None
        await self._db.flush()
        if self._run:
            if created:
                self._run.ads_created += 1
            else:
                self._run.ads_updated += 1
        return obj

    # ── Images ──────────────────────────────────────────────────

    async def _import_images(self) -> None:
        async for raw in self._client.iter_ad_images(self._account_external_id):
            img_hash = raw.get("hash", "")
            if not img_hash:
                continue
            await self._upsert_asset(raw)

    async def _upsert_asset(self, raw: dict[str, Any]) -> SourceAsset:
        img_hash = raw["hash"]
        result = await self._db.execute(
            select(SourceAsset).where(
                SourceAsset.organization_id == self._org_id,
                SourceAsset.image_hash == img_hash,
            )
        )
        obj = result.scalar_one_or_none()
        created = obj is None
        if obj is None:
            obj = SourceAsset(
                organization_id=self._org_id,
                image_hash=img_hash,
                source=self._source,
                is_fictitious=self._fictitious,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)
        obj.name = raw.get("name")
        obj.width = raw.get("width")
        obj.height = raw.get("height")
        obj.bytes_size = raw.get("bytes")
        # Source URL is stored as-is from Meta CDN; we do NOT download in Phase 2
        # (SSRF guard + download logic is documented as Phase 2+ enhancement)
        obj.source_url = raw.get("url")
        obj.raw_response = _redact_raw(raw)
        await self._db.flush()
        if self._run and created:
            self._run.assets_created += 1
        return obj

    # ── Insights → Snapshots ─────────────────────────────────────

    async def _import_insights(self, date_start: str, date_stop: str) -> None:
        async for raw in self._client.iter_insights(
            self._account_external_id,
            level="ad",
            date_start=date_start,
            date_stop=date_stop,
        ):
            ad_ext_id = raw.get("ad_id", "")
            if not ad_ext_id:
                continue
            ad_internal_id = self._ad_map.get(ad_ext_id)
            if not ad_internal_id:
                # Insight for an ad we don't have locally — look up by external_id
                result = await self._db.execute(
                    select(SourceAd).where(
                        SourceAd.organization_id == self._org_id,
                        SourceAd.external_id == ad_ext_id,
                    )
                )
                ad_obj = result.scalar_one_or_none()
                if not ad_obj:
                    logger.warning("meta_import_insight_no_ad", ad_ext_id=ad_ext_id)
                    continue
                ad_internal_id = ad_obj.id

            norm = _normalizer.normalize(raw)
            request_id = raw.get("_request_id", "")
            row_start = raw.get("date_start") or date_start
            row_stop = raw.get("date_stop") or date_stop

            await self._upsert_snapshot(
                source_ad_id=ad_internal_id,
                date_start=row_start,
                date_stop=row_stop,
                norm=norm,
                raw=_redact_raw(raw),
                request_id=request_id,
            )

    async def _upsert_snapshot(
        self,
        source_ad_id: uuid.UUID,
        date_start: str,
        date_stop: str,
        norm: Any,
        raw: dict[str, Any],
        request_id: str,
    ) -> None:
        result = await self._db.execute(
            select(PerformanceSnapshot).where(
                PerformanceSnapshot.organization_id == self._org_id,
                PerformanceSnapshot.source_ad_id == source_ad_id,
                PerformanceSnapshot.date_start == date_start,
                PerformanceSnapshot.date_stop == date_stop,
                PerformanceSnapshot.level == "ad",
                PerformanceSnapshot.breakdown_key == "",
            )
        )
        obj = result.scalar_one_or_none()
        created = obj is None
        if obj is None:
            obj = PerformanceSnapshot(
                organization_id=self._org_id,
                source_ad_id=source_ad_id,
                date_start=date_start,
                date_stop=date_stop,
                level="ad",
                breakdown_key="",
                is_fictitious=self._fictitious,
                metadata_={"fictitious": self._fictitious} if self._fictitious else None,
            )
            self._db.add(obj)

        obj.impressions = norm.impressions
        obj.reach = norm.reach
        obj.frequency = norm.frequency
        obj.spend = norm.spend
        obj.clicks = norm.clicks
        obj.link_clicks = norm.link_clicks
        obj.ctr = norm.ctr
        obj.cpc = norm.cpc
        obj.cpm = norm.cpm
        obj.landing_page_views = norm.landing_page_views
        obj.adds_to_cart = norm.adds_to_cart
        obj.initiate_checkout = norm.initiate_checkout
        obj.purchases = norm.purchases
        obj.leads = norm.leads
        obj.cost_per_result = norm.cost_per_result
        obj.purchase_value = norm.purchase_value
        obj.roas = norm.roas
        obj.roas_source = norm.roas_source
        obj.currency = norm.currency
        obj.attribution_window = norm.attribution_window
        obj.request_id = request_id
        obj.normalization_version = NORMALIZATION_VERSION
        obj.sync_run_id = self._run.id if self._run else None
        # Preserve unmapped actions in metadata
        if norm.unmapped_actions:
            obj.metadata_ = {
                **(obj.metadata_ or {}),
                "unmapped_actions": norm.unmapped_actions,
            }
        obj.raw_response = raw
        await self._db.flush()

        if self._run:
            if created:
                self._run.snapshots_created += 1
            else:
                self._run.snapshots_updated += 1

    # ── Run lifecycle ─────────────────────────────────────────────

    async def _create_run(self, kind: str, date_start: str, date_stop: str) -> MetaSyncRun:
        run = MetaSyncRun(
            organization_id=self._org_id,
            account_external_id=self._account_external_id,
            kind=kind,
            status="running",
            started_at=datetime.now(UTC),
            date_start=date_start,
            date_stop=date_stop,
        )
        self._db.add(run)
        await self._db.flush()
        await self._db.commit()
        return run

    async def _complete_run(self, run: MetaSyncRun, status: str) -> MetaSyncRun:
        run.status = status
        run.finished_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(run)
        return run

    async def _fail_run(self, run: MetaSyncRun, error: str) -> MetaSyncRun:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_detail = error[:2000]
        await self._db.commit()
        await self._db.refresh(run)
        return run


# ── Helpers ───────────────────────────────────────────────────────

def _budget(v: Any) -> float | None:
    if v is None or v == "0":
        return None
    try:
        cents = float(str(v))
        return cents / 100.0
    except (ValueError, TypeError):
        return None


def _redact_raw(d: dict[str, Any]) -> dict[str, Any]:
    """Remove access_token / appsecret_proof from raw response before persisting."""
    return {
        k: "***REDACTED***" if any(s in k.lower() for s in ("access_token", "appsecret_proof")) else v
        for k, v in d.items()
        if k != "_request_id"  # internal transport field, not from Meta
    }


def _run_summary(run: MetaSyncRun) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "status": run.status,
        "campaigns": run.campaigns_created + run.campaigns_updated,
        "adsets": run.adsets_created + run.adsets_updated,
        "ads": run.ads_created + run.ads_updated,
        "snapshots": run.snapshots_created + run.snapshots_updated,
    }
