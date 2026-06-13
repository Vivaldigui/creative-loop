from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class Experiment(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    # EXPLORATORY | CONTROLLED
    mode: Mapped[str] = mapped_column(String(20), default="CONTROLLED", nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_variable: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # draft | scheduled | running | evaluating | completed | stopped
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    # Phase 1 legacy criteria (kept for backward compat with seed data)
    min_spend: Mapped[float | None] = mapped_column(nullable=True)
    min_impressions: Mapped[int | None] = mapped_column(nullable=True)
    min_days: Mapped[int | None] = mapped_column(nullable=True)

    # Phase 7 — extended fields
    objective: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("products.id"), nullable=True, index=True
    )
    audience: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    placement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    primary_metric: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secondary_metrics: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    # FK to the baseline variant (is_control=True)
    baseline_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiment_variants.id", use_alter=True, name="fk_experiment_baseline_variant"),
        nullable=True,
    )
    # Configurable minimum criteria JSON: min_spend, min_impressions, min_clicks,
    # min_conversions, min_days, min_difference, min_confidence, max_frequency, maturation_window_days
    min_criteria: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # Last evaluation state from the motor
    evaluation_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # winner_candidate | inconclusive | safety | manual | budget_exhausted | window_ended
    stop_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    variants: Mapped[list[ExperimentVariant]] = relationship(
        "ExperimentVariant",
        back_populates="experiment",
        foreign_keys="ExperimentVariant.experiment_id",
    )
    evaluations: Mapped[list[ExperimentEvaluation]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExperimentEvaluation", back_populates="experiment"
    )
    decisions: Mapped[list[OptimizationDecision]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OptimizationDecision", back_populates="experiment"
    )


class ExperimentVariant(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "experiment_variants"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=False, index=True
    )
    creative_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_control: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Phase 7 — extended fields
    # control | test
    variant_role: Mapped[str] = mapped_column(String(20), default="test", nullable=False)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("prompt_versions.id"), nullable=True
    )
    published_ad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("published_ads.id"), nullable=True
    )
    # Variables changed vs. baseline — single item for CONTROLLED, multiple for EXPLORATORY
    changed_variables: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    allocated_budget: Mapped[float | None] = mapped_column(Float, nullable=True)

    experiment: Mapped[Experiment] = relationship(
        "Experiment",
        back_populates="variants",
        foreign_keys=[experiment_id],
    )
    metric_snapshots: Mapped[list[VariantPerformanceSnapshot]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "VariantPerformanceSnapshot", back_populates="variant"
    )
