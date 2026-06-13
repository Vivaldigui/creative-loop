"""phase2_meta_import

Revision ID: b4c8f2a1e9d3
Revises: 3e52a51ad4ff
Create Date: 2026-06-10 14:00:00.000000

Phase 2: Meta read-only import.
- New tables: ad_accounts, source_campaigns, source_adsets, source_creatives,
              source_assets, meta_sync_runs
- Extended: source_ads (hierarchy FKs, status fields, sync metadata)
- Extended: performance_snapshots (level, breakdown_key, currency, attribution,
            request_id, normalization_version, sync_run_id, roas_source,
            unique constraint for idempotency)

Note on unique constraint on performance_snapshots:
  NULL values for level/breakdown_key (Phase 1 seed rows) are treated as
  NULLS DISTINCT by both SQLite and PostgreSQL, so seed rows never conflict
  with Phase 2 synced rows (which always have level="ad", breakdown_key="").
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db

revision: str = "b4c8f2a1e9d3"
down_revision: Union[str, None] = "3e52a51ad4ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ad_accounts ──────────────────────────────────────────────
    op.create_table(
        "ad_accounts",
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(400), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("timezone_name", sa.String(100), nullable=True),
        sa.Column("account_status", sa.Integer(), nullable=True),
        sa.Column("business_id", sa.String(100), nullable=True),
        sa.Column("raw_response", app.db.JSONBType(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_ad_accounts_org_ext"),
    )
    op.create_index("ix_ad_accounts_external_id", "ad_accounts", ["external_id"], unique=False)
    op.create_index("ix_ad_accounts_organization_id", "ad_accounts", ["organization_id"], unique=False)
    op.create_index("ix_ad_accounts_business_id", "ad_accounts", ["business_id"], unique=False)

    # ── source_campaigns ─────────────────────────────────────────
    op.create_table(
        "source_campaigns",
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("ad_account_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("name", sa.String(400), nullable=False),
        sa.Column("objective", sa.String(100), nullable=True),
        sa.Column("effective_status", sa.String(50), nullable=True),
        sa.Column("configured_status", sa.String(50), nullable=True),
        sa.Column("buying_type", sa.String(50), nullable=True),
        sa.Column("daily_budget", sa.Float(), nullable=True),
        sa.Column("lifetime_budget", sa.Float(), nullable=True),
        sa.Column("raw_response", app.db.JSONBType(), nullable=True),
        sa.Column("sync_run_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("is_fictitious", sa.Boolean(), nullable=False),
        sa.Column("id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_source_campaigns_org_ext"),
    )
    op.create_index("ix_source_campaigns_external_id", "source_campaigns", ["external_id"], unique=False)
    op.create_index("ix_source_campaigns_organization_id", "source_campaigns", ["organization_id"], unique=False)
    op.create_index("ix_source_campaigns_ad_account_id", "source_campaigns", ["ad_account_id"], unique=False)
    op.create_index("ix_source_campaigns_sync_run_id", "source_campaigns", ["sync_run_id"], unique=False)

    # ── source_adsets ─────────────────────────────────────────────
    op.create_table(
        "source_adsets",
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("campaign_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("name", sa.String(400), nullable=False),
        sa.Column("optimization_goal", sa.String(100), nullable=True),
        sa.Column("billing_event", sa.String(50), nullable=True),
        sa.Column("bid_strategy", sa.String(50), nullable=True),
        sa.Column("targeting_summary", app.db.JSONBType(), nullable=True),
        sa.Column("daily_budget", sa.Float(), nullable=True),
        sa.Column("lifetime_budget", sa.Float(), nullable=True),
        sa.Column("effective_status", sa.String(50), nullable=True),
        sa.Column("raw_response", app.db.JSONBType(), nullable=True),
        sa.Column("sync_run_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("is_fictitious", sa.Boolean(), nullable=False),
        sa.Column("id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["source_campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_source_adsets_org_ext"),
    )
    op.create_index("ix_source_adsets_external_id", "source_adsets", ["external_id"], unique=False)
    op.create_index("ix_source_adsets_organization_id", "source_adsets", ["organization_id"], unique=False)
    op.create_index("ix_source_adsets_campaign_id", "source_adsets", ["campaign_id"], unique=False)

    # ── source_creatives ──────────────────────────────────────────
    op.create_table(
        "source_creatives",
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(400), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("cta_type", sa.String(100), nullable=True),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column("image_hash", sa.String(100), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("object_story_spec", app.db.JSONBType(), nullable=True),
        sa.Column("raw_response", app.db.JSONBType(), nullable=True),
        sa.Column("sync_run_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("is_fictitious", sa.Boolean(), nullable=False),
        sa.Column("id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_source_creatives_org_ext"),
    )
    op.create_index("ix_source_creatives_external_id", "source_creatives", ["external_id"], unique=False)
    op.create_index("ix_source_creatives_organization_id", "source_creatives", ["organization_id"], unique=False)
    op.create_index("ix_source_creatives_image_hash", "source_creatives", ["image_hash"], unique=False)

    # ── source_assets ─────────────────────────────────────────────
    op.create_table(
        "source_assets",
        sa.Column("image_hash", sa.String(100), nullable=False),
        sa.Column("name", sa.String(400), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("s3_key", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("bytes_size", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(100), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(50), nullable=True),
        sa.Column("raw_response", app.db.JSONBType(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("is_fictitious", sa.Boolean(), nullable=False),
        sa.Column("id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "image_hash", name="uq_source_assets_org_hash"),
    )
    op.create_index("ix_source_assets_image_hash", "source_assets", ["image_hash"], unique=False)
    op.create_index("ix_source_assets_organization_id", "source_assets", ["organization_id"], unique=False)
    op.create_index("ix_source_assets_sha256", "source_assets", ["sha256"], unique=False)

    # ── meta_sync_runs ────────────────────────────────────────────
    op.create_table(
        "meta_sync_runs",
        sa.Column("account_external_id", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_start", sa.String(20), nullable=True),
        sa.Column("date_stop", sa.String(20), nullable=True),
        sa.Column("campaigns_created", sa.Integer(), nullable=False),
        sa.Column("campaigns_updated", sa.Integer(), nullable=False),
        sa.Column("adsets_created", sa.Integer(), nullable=False),
        sa.Column("adsets_updated", sa.Integer(), nullable=False),
        sa.Column("ads_created", sa.Integer(), nullable=False),
        sa.Column("ads_updated", sa.Integer(), nullable=False),
        sa.Column("creatives_created", sa.Integer(), nullable=False),
        sa.Column("creatives_updated", sa.Integer(), nullable=False),
        sa.Column("snapshots_created", sa.Integer(), nullable=False),
        sa.Column("snapshots_updated", sa.Integer(), nullable=False),
        sa.Column("assets_created", sa.Integer(), nullable=False),
        sa.Column("cursor_checkpoint", sa.Text(), nullable=True),
        sa.Column("request_ids", app.db.JSONBType(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meta_sync_runs_organization_id", "meta_sync_runs", ["organization_id"], unique=False)
    op.create_index("ix_meta_sync_runs_account_external_id", "meta_sync_runs", ["account_external_id"], unique=False)

    # ── source_ads: new columns (all nullable for Phase 1 compat) ─
    op.add_column("source_ads", sa.Column("source_adset_id", app.db.UUIDType(length=36), nullable=True))
    op.add_column("source_ads", sa.Column("source_creative_id", app.db.UUIDType(length=36), nullable=True))
    op.add_column("source_ads", sa.Column("effective_status", sa.String(50), nullable=True))
    op.add_column("source_ads", sa.Column("configured_status", sa.String(50), nullable=True))
    op.add_column("source_ads", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_ads", sa.Column("sync_run_id", app.db.UUIDType(length=36), nullable=True))
    op.add_column("source_ads", sa.Column("source", sa.String(50), nullable=True))
    op.create_index("ix_source_ads_source_adset_id", "source_ads", ["source_adset_id"], unique=False)
    op.create_index("ix_source_ads_source_creative_id", "source_ads", ["source_creative_id"], unique=False)
    op.create_index("ix_source_ads_sync_run_id", "source_ads", ["sync_run_id"], unique=False)

    # ── performance_snapshots: new columns + unique constraint ────
    op.add_column("performance_snapshots", sa.Column("level", sa.String(20), nullable=True))
    op.add_column("performance_snapshots", sa.Column("breakdown_key", sa.String(100), nullable=True))
    op.add_column("performance_snapshots", sa.Column("attribution_window", sa.String(50), nullable=True))
    op.add_column("performance_snapshots", sa.Column("currency", sa.String(10), nullable=True))
    op.add_column("performance_snapshots", sa.Column("request_id", sa.String(200), nullable=True))
    op.add_column("performance_snapshots", sa.Column("normalization_version", sa.String(20), nullable=True))
    op.add_column("performance_snapshots", sa.Column("sync_run_id", app.db.UUIDType(length=36), nullable=True))
    op.add_column("performance_snapshots", sa.Column("roas_source", sa.String(20), nullable=True))
    op.create_index("ix_performance_snapshots_sync_run_id", "performance_snapshots", ["sync_run_id"], unique=False)
    op.create_index(
        "uq_perf_snapshot_key",
        "performance_snapshots",
        ["source_ad_id", "date_start", "date_stop", "level", "breakdown_key"],
        unique=True,
    )


def downgrade() -> None:
    # performance_snapshots
    op.drop_index("uq_perf_snapshot_key", table_name="performance_snapshots")
    op.drop_index("ix_performance_snapshots_sync_run_id", table_name="performance_snapshots")
    for col in ("roas_source", "sync_run_id", "normalization_version", "request_id",
                "currency", "attribution_window", "breakdown_key", "level"):
        op.drop_column("performance_snapshots", col)

    # source_ads
    for idx in ("ix_source_ads_sync_run_id", "ix_source_ads_source_creative_id", "ix_source_ads_source_adset_id"):
        op.drop_index(idx, table_name="source_ads")
    for col in ("source", "sync_run_id", "last_synced_at", "configured_status",
                "effective_status", "source_creative_id", "source_adset_id"):
        op.drop_column("source_ads", col)

    # new tables
    op.drop_index("ix_meta_sync_runs_account_external_id", table_name="meta_sync_runs")
    op.drop_index("ix_meta_sync_runs_organization_id", table_name="meta_sync_runs")
    op.drop_table("meta_sync_runs")

    op.drop_index("ix_source_assets_sha256", table_name="source_assets")
    op.drop_index("ix_source_assets_organization_id", table_name="source_assets")
    op.drop_index("ix_source_assets_image_hash", table_name="source_assets")
    op.drop_table("source_assets")

    op.drop_index("ix_source_creatives_image_hash", table_name="source_creatives")
    op.drop_index("ix_source_creatives_organization_id", table_name="source_creatives")
    op.drop_index("ix_source_creatives_external_id", table_name="source_creatives")
    op.drop_table("source_creatives")

    op.drop_index("ix_source_adsets_campaign_id", table_name="source_adsets")
    op.drop_index("ix_source_adsets_organization_id", table_name="source_adsets")
    op.drop_index("ix_source_adsets_external_id", table_name="source_adsets")
    op.drop_table("source_adsets")

    op.drop_index("ix_source_campaigns_sync_run_id", table_name="source_campaigns")
    op.drop_index("ix_source_campaigns_ad_account_id", table_name="source_campaigns")
    op.drop_index("ix_source_campaigns_organization_id", table_name="source_campaigns")
    op.drop_index("ix_source_campaigns_external_id", table_name="source_campaigns")
    op.drop_table("source_campaigns")

    op.drop_index("ix_ad_accounts_business_id", table_name="ad_accounts")
    op.drop_index("ix_ad_accounts_organization_id", table_name="ad_accounts")
    op.drop_index("ix_ad_accounts_external_id", table_name="ad_accounts")
    op.drop_table("ad_accounts")
