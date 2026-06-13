"""phase4_creatives_storage

Phase 4: creative_assets table, new columns on generated_creatives and approvals.

Revision ID: d1e2f3a4b5c6
Revises: c7d9e3f1a2b4
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.db

revision = "d1e2f3a4b5c6"
down_revision = "c7d9e3f1a2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── creative_assets (new table) ──────────────────────────────
    op.create_table(
        "creative_assets",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column("organization_id", app.db.UUIDType(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "creative_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("generated_creatives.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("format_label", sa.String(50), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "storage_backend", sa.String(20), nullable=False, server_default="local"
        ),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(50), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("fit_strategy", sa.String(20), nullable=True),
        sa.Column(
            "is_fictitious", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_creative_assets_organization_id", "creative_assets", ["organization_id"]
    )
    op.create_index(
        "ix_creative_assets_creative_id", "creative_assets", ["creative_id"]
    )
    op.create_index("ix_creative_assets_file_hash", "creative_assets", ["file_hash"])

    # ── generated_creatives — new columns ────────────────────────
    op.add_column(
        "generated_creatives", sa.Column("storage_key", sa.Text(), nullable=True)
    )
    op.add_column(
        "generated_creatives",
        sa.Column("storage_backend", sa.String(20), nullable=True),
    )
    op.add_column(
        "generated_creatives", sa.Column("phash", sa.String(64), nullable=True)
    )
    op.add_column(
        "generated_creatives",
        sa.Column("variation_of_id", app.db.UUIDType(length=36), nullable=True),
    )
    op.add_column(
        "generated_creatives",
        sa.Column("source_ad_id", app.db.UUIDType(length=36), nullable=True),
    )
    op.create_index("ix_generated_creatives_phash", "generated_creatives", ["phash"])
    op.create_index(
        "ix_generated_creatives_source_ad_id", "generated_creatives", ["source_ad_id"]
    )

    # ── approvals — new columns ───────────────────────────────────
    op.add_column("approvals", sa.Column("action", sa.String(30), nullable=True))
    op.add_column(
        "approvals", sa.Column("overridden_check_ids", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("approvals", "overridden_check_ids")
    op.drop_column("approvals", "action")
    op.drop_index("ix_generated_creatives_source_ad_id", "generated_creatives")
    op.drop_index("ix_generated_creatives_phash", "generated_creatives")
    op.drop_column("generated_creatives", "source_ad_id")
    op.drop_column("generated_creatives", "variation_of_id")
    op.drop_column("generated_creatives", "phash")
    op.drop_column("generated_creatives", "storage_backend")
    op.drop_column("generated_creatives", "storage_key")
    op.drop_index("ix_creative_assets_file_hash", "creative_assets")
    op.drop_index("ix_creative_assets_creative_id", "creative_assets")
    op.drop_index("ix_creative_assets_organization_id", "creative_assets")
    op.drop_table("creative_assets")
