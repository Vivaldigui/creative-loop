"""phase5_publication_dryrun

Phase 5: publication_drafts table, publication_attempts table,
and new traceability columns on audit_logs.

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.db

revision = "e5f6a7b8c9d0"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── publication_drafts ───────────────────────────────────────
    op.create_table(
        "publication_drafts",
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
        sa.Column(
            "experiment_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("experiments.id"),
            nullable=True,
        ),
        sa.Column("campaign_config", sa.JSON(), nullable=True),
        sa.Column("adset_config", sa.JSON(), nullable=True),
        sa.Column("ad_config", sa.JSON(), nullable=True),
        sa.Column("landing_url", sa.Text(), nullable=True),
        sa.Column("tracking_params", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column(
            "is_fictitious", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_publication_drafts_organization_id",
        "publication_drafts",
        ["organization_id"],
    )
    op.create_index(
        "ix_publication_drafts_creative_id", "publication_drafts", ["creative_id"]
    )
    op.create_index(
        "ix_publication_drafts_experiment_id", "publication_drafts", ["experiment_id"]
    )
    op.create_index(
        "ix_publication_drafts_payload_hash", "publication_drafts", ["payload_hash"]
    )
    op.create_index("ix_publication_drafts_status", "publication_drafts", ["status"])

    # ── publication_attempts ─────────────────────────────────────
    op.create_table(
        "publication_attempts",
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
            "draft_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("publication_drafts.id"),
            nullable=True,
        ),
        sa.Column(
            "creative_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("generated_creatives.id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="DRY_RUN"),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("checks", sa.JSON(), nullable=True),
        sa.Column("simulated_response", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "published_ad_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("published_ads.id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_attempt_org_idem_key"
        ),
    )
    op.create_index(
        "ix_publication_attempts_organization_id",
        "publication_attempts",
        ["organization_id"],
    )
    op.create_index(
        "ix_publication_attempts_creative_id", "publication_attempts", ["creative_id"]
    )
    op.create_index(
        "ix_publication_attempts_draft_id", "publication_attempts", ["draft_id"]
    )
    op.create_index(
        "ix_publication_attempts_idempotency_key",
        "publication_attempts",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_publication_attempts_payload_hash", "publication_attempts", ["payload_hash"]
    )
    op.create_index(
        "ix_publication_attempts_correlation_id",
        "publication_attempts",
        ["correlation_id"],
    )
    op.create_index(
        "ix_publication_attempts_result", "publication_attempts", ["result"]
    )

    # ── audit_logs — Phase 5 traceability columns ─────────────────
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("correlation_id", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("approval_id", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("limits_checked", sa.JSON(), nullable=True))

    op.create_index("ix_audit_logs_idempotency_key", "audit_logs", ["idempotency_key"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_idempotency_key", table_name="audit_logs")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_column("limits_checked")
        batch_op.drop_column("approval_id")
        batch_op.drop_column("correlation_id")
        batch_op.drop_column("idempotency_key")

    op.drop_table("publication_attempts")
    op.drop_table("publication_drafts")
