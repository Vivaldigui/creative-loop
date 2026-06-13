"""Backfill NULL variant_role in experiment_variants based on is_control flag.

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j9k0l1m2n3o4"
down_revision = "i8j9k0l1m2n3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    variants = sa.table(
        "experiment_variants",
        sa.column("variant_role", sa.String()),
        sa.column("is_control", sa.Boolean()),
    )
    conn.execute(
        variants.update()
        .where(
            sa.and_(
                variants.c.is_control.is_(True),
                sa.or_(
                    variants.c.variant_role.is_(None), variants.c.variant_role == ""
                ),
            )
        )
        .values(variant_role="control")
    )
    conn.execute(
        variants.update()
        .where(
            sa.and_(
                variants.c.is_control.is_(False),
                sa.or_(
                    variants.c.variant_role.is_(None), variants.c.variant_role == ""
                ),
            )
        )
        .values(variant_role="test")
    )


def downgrade() -> None:
    pass
