from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class AdAccount(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Meta ad account associated with an organisation."""

    __tablename__ = "ad_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_ad_accounts_org_ext"),
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(400), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    timezone_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # real | mock


class SourceCampaign(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Historical campaign imported from Meta."""

    __tablename__ = "source_campaigns"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_source_campaigns_org_ext"),
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ad_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("ad_accounts.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    objective: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    configured_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buying_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    daily_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    lifetime_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    adsets: Mapped[list[SourceAdSet]] = relationship("SourceAdSet", back_populates="campaign")


class SourceAdSet(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Historical ad set imported from Meta."""

    __tablename__ = "source_adsets"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_source_adsets_org_ext"),
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("source_campaigns.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    optimization_goal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    billing_event: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bid_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    targeting_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    daily_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    lifetime_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    campaign: Mapped[SourceCampaign | None] = relationship("SourceCampaign", back_populates="adsets")


class SourceCreative(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Meta ad creative (format + copy + media spec)."""

    __tablename__ = "source_creatives"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_source_creatives_org_ext"),
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(400), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_hash: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_story_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    sync_run_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)


class SourceAsset(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Image file belonging to the authorised ad account."""

    __tablename__ = "source_assets"
    __table_args__ = (
        UniqueConstraint("organization_id", "image_hash", name="uq_source_assets_org_hash"),
    )

    image_hash: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(400), nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)


class MetaSyncRun(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Audit record for each Meta import execution."""

    __tablename__ = "meta_sync_runs"

    account_external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # history | incremental
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_stop: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Counters
    campaigns_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    campaigns_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adsets_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adsets_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ads_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ads_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    creatives_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    creatives_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshots_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshots_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assets_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Resumption / audit
    cursor_checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_ids: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
