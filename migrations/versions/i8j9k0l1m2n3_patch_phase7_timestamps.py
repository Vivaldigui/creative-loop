"""Backfill NULL created_at/updated_at in Phase 7 tables and add server defaults.

Revision ID: i8j9k0l1m2n3
Revises: h7g6f5e4d3c2
Create Date: 2026-06-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i8j9k0l1m2n3"
down_revision = "h7g6f5e4d3c2"
branch_labels = None
depends_on = None

_PHASE7_TABLES = [
    "experiments",
    "experiment_variants",
    "experiment_evaluations",
    "experiment_suggestions",
    "learnings",
    "variant_performance_snapshots",
]


def upgrade() -> None:
    conn = op.get_bind()
    # Backfill NULLs in all Phase 7 tables
    for tbl in _PHASE7_TABLES:
        conn.execute(
            sa.text(
                f"UPDATE {tbl} SET created_at = CURRENT_TIMESTAMP"
                f" WHERE created_at IS NULL"
            )
        )
        conn.execute(
            sa.text(
                f"UPDATE {tbl} SET updated_at = CURRENT_TIMESTAMP"
                f" WHERE updated_at IS NULL"
            )
        )


def downgrade() -> None:
    pass
