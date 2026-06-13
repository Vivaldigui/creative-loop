"""Repair missing Phase 6 credential lifecycle columns.

Revision ID: k1l2m3n4o5p6
Revises: j9k0l1m2n3o4
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "k1l2m3n4o5p6"
down_revision = "j9k0l1m2n3o4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"]
        for column in sa.inspect(bind).get_columns("integration_credentials")
    }

    with op.batch_alter_table("integration_credentials") as batch_op:
        if "expires_at" not in existing:
            batch_op.add_column(
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
            )
        if "scopes" not in existing:
            batch_op.add_column(sa.Column("scopes", sa.JSON(), nullable=True))
        if "last_health_status" not in existing:
            batch_op.add_column(
                sa.Column("last_health_status", sa.String(length=50), nullable=True)
            )


def downgrade() -> None:
    # This repair may adopt columns created by the original Phase 6 migration.
    # Removing them here could destroy valid production data.
    pass
