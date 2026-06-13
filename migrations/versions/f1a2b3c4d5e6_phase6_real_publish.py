"""phase6_real_publish

Phase 6: real Meta publish workflow.
- publication_steps table (per-step audit trail)
- extend published_ads (effective_status, lifecycle timestamps, activation, rejection)
- extend publication_attempts (meta_request_ids)
- extend audit_logs (emergency flag)
- extend integration_credentials (expires_at, scopes)

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.db

revision = "f1a2b3c4d5e6"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── publication_steps (new) ─────────────────────────────────────
    op.create_table(
        "publication_steps",
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
        sa.Column(
            "attempt_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("publication_attempts.id"),
            nullable=False,
        ),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("meta_node_id", sa.String(200), nullable=True),
        sa.Column("meta_request_id", sa.String(200), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "is_recoverable", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("step_payload", sa.JSON(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_publication_steps_attempt_id", "publication_steps", ["attempt_id"]
    )
    op.create_index("ix_publication_steps_state", "publication_steps", ["state"])
    op.create_index(
        "ix_publication_steps_organization_id", "publication_steps", ["organization_id"]
    )

    # ── published_ads — Phase 6 columns ────────────────────────────
    with op.batch_alter_table("published_ads") as batch_op:
        batch_op.add_column(sa.Column("effective_status", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("workflow_state", sa.String(50), nullable=True))
        batch_op.add_column(
            sa.Column(
                "last_status_checked_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("activated_by", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("paused_by", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("idempotency_tag", sa.String(200), nullable=True))

    # ── publication_attempts — Phase 6 columns ──────────────────────
    with op.batch_alter_table("publication_attempts") as batch_op:
        batch_op.add_column(sa.Column("meta_request_ids", sa.JSON(), nullable=True))

    # ── audit_logs — Phase 6 columns ────────────────────────────────
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "emergency", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    # ── integration_credentials — Phase 6 columns ───────────────────
    with op.batch_alter_table("integration_credentials") as batch_op:
        batch_op.add_column(
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("scopes", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("last_health_status", sa.String(50), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("integration_credentials") as batch_op:
        batch_op.drop_column("last_health_status")
        batch_op.drop_column("scopes")
        batch_op.drop_column("expires_at")

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_column("emergency")

    with op.batch_alter_table("publication_attempts") as batch_op:
        batch_op.drop_column("meta_request_ids")

    with op.batch_alter_table("published_ads") as batch_op:
        batch_op.drop_column("idempotency_tag")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("paused_by")
        batch_op.drop_column("paused_at")
        batch_op.drop_column("activated_by")
        batch_op.drop_column("activated_at")
        batch_op.drop_column("last_status_checked_at")
        batch_op.drop_column("workflow_state")
        batch_op.drop_column("effective_status")

    op.drop_index(
        "ix_publication_steps_organization_id", table_name="publication_steps"
    )
    op.drop_index("ix_publication_steps_state", table_name="publication_steps")
    op.drop_index("ix_publication_steps_attempt_id", table_name="publication_steps")
    op.drop_table("publication_steps")
