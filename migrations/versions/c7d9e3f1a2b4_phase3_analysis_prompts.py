"""phase3 analysis prompts

Revision ID: c7d9e3f1a2b4
Revises: b4c8f2a1e9d3
Create Date: 2026-06-10 19:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

import app.db

revision = "c7d9e3f1a2b4"
down_revision = "b4c8f2a1e9d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    json_type = sa.Text() if not is_pg else sa.JSON()

    # ── 1. creative_hypotheses ────────────────────────────────────
    # if_not_exists not supported by Alembic create_table; table is freshly created here
    op.create_table(
        "creative_hypotheses",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
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
        sa.Column("metadata", json_type, nullable=True),
        sa.Column(
            "source_ad_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("source_ads.id"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            app.db.UUIDType(length=36),
            sa.ForeignKey("creative_analyses.id"),
            nullable=False,
        ),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("primary_variable", sa.String(100), nullable=True),
        sa.Column("expected_effect", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "is_fictitious", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_creative_hypotheses_source_ad_id", "creative_hypotheses", ["source_ad_id"]
    )
    op.create_index(
        "ix_creative_hypotheses_analysis_id", "creative_hypotheses", ["analysis_id"]
    )

    # ── 2. ALTER creative_analyses ────────────────────────────────
    op.add_column(
        "creative_analyses", sa.Column("input_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "creative_analyses",
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "creative_analyses", sa.Column("media_kind", sa.String(20), nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("observations", json_type, nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("metric_facts", json_type, nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("limitations", json_type, nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("request_metadata", json_type, nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("parameters", json_type, nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("prompt_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("output_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("estimated_cost_usd", sa.Float(), nullable=True)
    )
    op.add_column(
        "creative_analyses", sa.Column("latency_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "creative_analyses",
        sa.Column("repaired", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "creative_analyses", sa.Column("error_detail", sa.Text(), nullable=True)
    )
    op.create_index(
        "ix_analysis_input_hash",
        "creative_analyses",
        ["organization_id", "source_ad_id", "input_hash"],
    )

    # ── 3. ALTER prompt_templates ─────────────────────────────────
    with op.batch_alter_table("prompt_templates") as batch_op:
        batch_op.add_column(
            sa.Column("hypothesis_id", app.db.UUIDType(length=36), nullable=True)
        )
    op.create_index(
        "ix_prompt_templates_hypothesis_id", "prompt_templates", ["hypothesis_id"]
    )

    # ── 4. ALTER prompt_versions ──────────────────────────────────
    op.add_column(
        "prompt_versions", sa.Column("content_hash", sa.String(64), nullable=True)
    )
    op.add_column(
        "prompt_versions",
        sa.Column("author_type", sa.String(20), nullable=False, server_default="human"),
    )
    op.add_column(
        "prompt_versions", sa.Column("target_model", sa.String(100), nullable=True)
    )
    op.add_column(
        "prompt_versions", sa.Column("generation_parameters", json_type, nullable=True)
    )
    op.create_index(
        "ix_prompt_versions_content_hash", "prompt_versions", ["content_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_versions_content_hash", "prompt_versions")
    op.drop_column("prompt_versions", "generation_parameters")
    op.drop_column("prompt_versions", "target_model")
    op.drop_column("prompt_versions", "author_type")
    op.drop_column("prompt_versions", "content_hash")

    op.drop_index("ix_prompt_templates_hypothesis_id", "prompt_templates")
    op.drop_column("prompt_templates", "hypothesis_id")

    op.drop_index("ix_analysis_input_hash", "creative_analyses")
    for col in [
        "error_detail",
        "repaired",
        "latency_ms",
        "estimated_cost_usd",
        "output_tokens",
        "prompt_tokens",
        "parameters",
        "request_metadata",
        "limitations",
        "metric_facts",
        "observations",
        "media_kind",
        "analysis_version",
        "input_hash",
    ]:
        op.drop_column("creative_analyses", col)

    op.drop_index("ix_creative_hypotheses_analysis_id", "creative_hypotheses")
    op.drop_index("ix_creative_hypotheses_source_ad_id", "creative_hypotheses")
    op.drop_table("creative_hypotheses")
