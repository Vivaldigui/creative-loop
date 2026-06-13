"""Add meta_image_hash to published_ads (missed in Phase 6).

Revision ID: h7g6f5e4d3c2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h7g6f5e4d3c2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("published_ads") as batch_op:
        batch_op.add_column(sa.Column("meta_image_hash", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("published_ads") as batch_op:
        batch_op.drop_column("meta_image_hash")
