from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class SourceAd(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Historical ad (real or fictitious). The starting point of the creative loop."""

    __tablename__ = "source_ads"

    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("products.id"), nullable=True, index=True
    )
    # Phase 1 fields
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta: Mapped[str | None] = mapped_column(String(100), nullable=True)
    landing_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    ad_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    placement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)
    performance_label: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # winner | loser | neutral
    # Phase 2 fields (nullable for backward compat with Phase 1 seed data)
    source_adset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("source_adsets.id"), nullable=True, index=True
    )
    source_creative_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("source_creatives.id"), nullable=True, index=True
    )
    effective_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    configured_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="source_ads")  # type: ignore[name-defined]  # noqa: F821
    source_adset: Mapped[SourceAdSet | None] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "SourceAdSet", foreign_keys=[source_adset_id]
    )
    source_creative: Mapped[SourceCreative | None] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "SourceCreative", foreign_keys=[source_creative_id]
    )
    snapshots: Mapped[list[PerformanceSnapshot]] = relationship(
        "PerformanceSnapshot", back_populates="source_ad"
    )
    analyses: Mapped[list[CreativeAnalysis]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CreativeAnalysis", back_populates="source_ad"
    )


class PerformanceSnapshot(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Metric snapshot for a source ad (from Meta Insights or fictitious)."""

    __tablename__ = "performance_snapshots"
    __table_args__ = (
        # Idempotency key: same ad + window + level + breakdown == same row (upsert target)
        # NULL level/breakdown_key are treated as distinct by SQL, so Phase 1 seed rows
        # (which have NULL for both) never conflict with Phase 2 synced rows.
        UniqueConstraint(
            "source_ad_id", "date_start", "date_stop", "level", "breakdown_key",
            name="uq_perf_snapshot_key",
        ),
    )

    source_ad_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("source_ads.id"), nullable=False, index=True
    )
    date_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_stop: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Core metrics — all nullable: not every account/objective returns all fields
    impressions: Mapped[int | None] = mapped_column(nullable=True)
    reach: Mapped[int | None] = mapped_column(nullable=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    clicks: Mapped[int | None] = mapped_column(nullable=True)
    link_clicks: Mapped[int | None] = mapped_column(nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    landing_page_views: Mapped[int | None] = mapped_column(nullable=True)
    adds_to_cart: Mapped[int | None] = mapped_column(nullable=True)
    initiate_checkout: Mapped[int | None] = mapped_column(nullable=True)
    purchases: Mapped[int | None] = mapped_column(nullable=True)
    leads: Mapped[int | None] = mapped_column(nullable=True)
    cost_per_result: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchase_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    roas: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Phase 2 fields
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ad | adset | campaign | account
    breakdown_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution_window: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    normalization_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    roas_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # reported | derived

    source_ad: Mapped[SourceAd] = relationship("SourceAd", back_populates="snapshots")
