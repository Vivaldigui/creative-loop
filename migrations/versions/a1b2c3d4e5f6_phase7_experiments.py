"""phase7_experiments

Phase 7: Experiments, evaluations, decisions, learnings, suggestions, variant metrics.

- experiment_variants: extend with variant_role, prompt_version_id, published_ad_id,
  changed_variables, allocated_budget
- experiments: extend with objective, product_id, audience, placement, window_start/end,
  planned_budget, currency, primary_metric, secondary_metrics, baseline_variant_id,
  min_criteria, evaluation_state, started_at, ended_at, stop_reason
- variant_performance_snapshots (new)
- experiment_evaluations (new)
- optimization_decisions (new)
- learnings (new)
- learning_usages (new)
- experiment_suggestions (new)

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

import app.db  # JSONBType (JSONB on PostgreSQL, JSON on SQLite)

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend experiment_variants ─────────────────────────────────
    with op.batch_alter_table("experiment_variants") as batch_op:
        batch_op.add_column(sa.Column("variant_role", sa.String(20), nullable=True))
        batch_op.add_column(
            sa.Column("prompt_version_id", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("published_ad_id", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("changed_variables", app.db.JSONBType(), nullable=True)
        )
        batch_op.add_column(sa.Column("allocated_budget", sa.Float(), nullable=True))

    # ── Extend experiments ─────────────────────────────────────────
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.add_column(sa.Column("objective", sa.String(100), nullable=True))
        batch_op.add_column(
            sa.Column("product_id", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("audience", app.db.JSONBType(), nullable=True))
        batch_op.add_column(sa.Column("placement", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("window_start", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("window_end", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("planned_budget", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("currency", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("primary_metric", sa.String(50), nullable=True))
        batch_op.add_column(
            sa.Column("secondary_metrics", app.db.JSONBType(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("baseline_variant_id", app.db.UUIDType(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("min_criteria", app.db.JSONBType(), nullable=True)
        )
        batch_op.add_column(sa.Column("evaluation_state", sa.String(50), nullable=True))
        batch_op.add_column(
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("stop_reason", sa.String(50), nullable=True))

    # ── variant_performance_snapshots (new) — mirrors VariantPerformanceSnapshot
    op.create_table(
        "variant_performance_snapshots",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "experiment_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column("variant_id", app.db.UUIDType(length=36), nullable=False, index=True),
        sa.Column(
            "published_ad_id", app.db.UUIDType(length=36), nullable=True, index=True
        ),
        sa.Column("meta_ad_id", sa.String(200), nullable=True, index=True),
        sa.Column("date_start", sa.String(20), nullable=True),
        sa.Column("date_stop", sa.String(20), nullable=True),
        # Core metrics — all nullable
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Float(), nullable=True),
        sa.Column("spend", sa.Float(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("link_clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("cpc", sa.Float(), nullable=True),
        sa.Column("cpm", sa.Float(), nullable=True),
        sa.Column("landing_page_views", sa.Integer(), nullable=True),
        sa.Column("adds_to_cart", sa.Integer(), nullable=True),
        sa.Column("initiate_checkout", sa.Integer(), nullable=True),
        sa.Column("purchases", sa.Integer(), nullable=True),
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("cost_per_result", sa.Float(), nullable=True),
        sa.Column("purchase_value", sa.Float(), nullable=True),
        sa.Column("roas", sa.Float(), nullable=True),
        sa.Column("raw_response", app.db.JSONBType(), nullable=True),
        # Maturation
        sa.Column(
            "is_matured", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "is_fictitious", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        # Normalizer provenance
        sa.Column("level", sa.String(20), nullable=True),
        sa.Column("breakdown_key", sa.String(100), nullable=True),
        sa.Column("attribution_window", sa.String(50), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("request_id", sa.String(200), nullable=True),
        sa.Column("normalization_version", sa.String(20), nullable=True),
        sa.Column("roas_source", sa.String(20), nullable=True),
        sa.Column("sync_run_id", app.db.UUIDType(length=36), nullable=True, index=True),
        # Mixins
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        # Unique constraint for idempotent upsert
        sa.UniqueConstraint(
            "variant_id",
            "date_start",
            "date_stop",
            "level",
            "breakdown_key",
            "attribution_window",
            name="uq_variant_snapshot_key",
        ),
    )

    # ── experiment_evaluations (new, append-only) — mirrors ExperimentEvaluation
    op.create_table(
        "experiment_evaluations",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "experiment_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_state", sa.String(50), nullable=False),
        sa.Column("primary_metric", sa.String(50), nullable=True),
        sa.Column("per_variant_result", app.db.JSONBType(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("data_window", app.db.JSONBType(), nullable=True),
        sa.Column("matured_through", sa.Date(), nullable=True),
        sa.Column("limitations", app.db.JSONBType(), nullable=True),
        sa.Column("total_snapshots_used", sa.Integer(), nullable=True),
        sa.Column(
            "engine_version", sa.String(20), nullable=False, server_default="1.0.0"
        ),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "causal_attribution",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_fictitious", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── optimization_decisions (new) — mirrors OptimizationDecision
    op.create_table(
        "optimization_decisions",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "experiment_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "evaluation_id", app.db.UUIDType(length=36), nullable=True, index=True
        ),
        sa.Column("data_used", app.db.JSONBType(), nullable=True),
        sa.Column("period_start", sa.String(20), nullable=True),
        sa.Column("period_end", sa.String(20), nullable=True),
        sa.Column("primary_metric", sa.String(50), nullable=True),
        sa.Column("result", app.db.JSONBType(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("limitations", app.db.JSONBType(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("suggested_action", sa.String(50), nullable=True),
        sa.Column("executed_action", sa.String(50), nullable=True),
        sa.Column("execution_notes", sa.Text(), nullable=True),
        sa.Column("user_responsible_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_log_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── learnings (new) — mirrors Learning ─────────────────────────
    op.create_table(
        "learnings",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("segment", sa.String(100), nullable=True),
        sa.Column("product_id", app.db.UUIDType(length=36), nullable=True, index=True),
        sa.Column("audience", app.db.JSONBType(), nullable=True),
        sa.Column("placement", sa.String(100), nullable=True),
        sa.Column("format", sa.String(50), nullable=True),
        sa.Column("objective", sa.String(100), nullable=True),
        sa.Column("observed_pattern", sa.Text(), nullable=False),
        sa.Column("evidence", app.db.JSONBType(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("metrics", app.db.JSONBType(), nullable=True),
        sa.Column("limitations", app.db.JSONBType(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "source_experiment_id",
            app.db.UUIDType(length=36),
            nullable=True,
            index=True,
        ),
        sa.Column("source_evaluation_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="provisional",
            index=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column(
            "responsible_type", sa.String(20), nullable=False, server_default="agent"
        ),
        sa.Column("embedding", app.db.JSONBType(), nullable=True),
        sa.Column("supersedes_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column(
            "is_fictitious", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("metadata", app.db.JSONBType(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── learning_usages (new) — mirrors LearningUsage ──────────────
    op.create_table(
        "learning_usages",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "learning_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "suggestion_id", app.db.UUIDType(length=36), nullable=True, index=True
        ),
        sa.Column("prompt_version_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── experiment_suggestions (new) — mirrors ExperimentSuggestion
    op.create_table(
        "experiment_suggestions",
        sa.Column("id", app.db.UUIDType(length=36), primary_key=True),
        sa.Column(
            "organization_id", app.db.UUIDType(length=36), nullable=False, index=True
        ),
        sa.Column(
            "source_experiment_id",
            app.db.UUIDType(length=36),
            nullable=False,
            index=True,
        ),
        sa.Column("draft_experiment_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("draft_prompt_version_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("selected_learning_ids", app.db.JSONBType(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("primary_variable", sa.String(100), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("diversity_score", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pending_approval",
            index=True,
        ),
        sa.Column("reviewed_by_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.String(500), nullable=True),
        sa.Column("audit_log_id", app.db.UUIDType(length=36), nullable=True),
        sa.Column("context_snapshot", app.db.JSONBType(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("experiment_suggestions")
    op.drop_table("learning_usages")
    op.drop_table("learnings")
    op.drop_table("optimization_decisions")
    op.drop_table("experiment_evaluations")
    op.drop_table("variant_performance_snapshots")

    with op.batch_alter_table("experiments") as batch_op:
        for col in [
            "objective",
            "product_id",
            "audience",
            "placement",
            "window_start",
            "window_end",
            "planned_budget",
            "currency",
            "primary_metric",
            "secondary_metrics",
            "baseline_variant_id",
            "min_criteria",
            "evaluation_state",
            "started_at",
            "ended_at",
            "stop_reason",
        ]:
            batch_op.drop_column(col)

    with op.batch_alter_table("experiment_variants") as batch_op:
        for col in [
            "variant_role",
            "prompt_version_id",
            "published_ad_id",
            "changed_variables",
            "allocated_budget",
        ]:
            batch_op.drop_column(col)
