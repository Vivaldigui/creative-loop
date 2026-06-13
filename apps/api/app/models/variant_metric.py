from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class VariantPerformanceSnapshot(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Metric snapshot for a specific experiment variant (mirrors PerformanceSnapshot schema)."""

    __tablename__ = "variant_performance_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "variant_id", "date_start", "date_stop", "level", "breakdown_key", "attribution_window",
            name="uq_variant_snapshot_key",
        ),
    )

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=False, index=True
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("experiment_variants.id"), nullable=False, index=True
    )
    published_ad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("published_ads.id"), nullable=True, index=True
    )
    meta_ad_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    date_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_stop: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Core metrics — nullable; not every account/objective returns all fields
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
    # True once the maturation_window_days has passed for this window
    is_matured: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Phase 2 normalizer provenance
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    breakdown_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution_window: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    normalization_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    roas_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # reported | derived
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)

    variant: Mapped[ExperimentVariant] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExperimentVariant", back_populates="metric_snapshots"
    )
