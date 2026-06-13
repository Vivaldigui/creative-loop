from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class ExperimentEvaluation(Base, UUIDMixin, OrgMixin, TimestampMixin):
    """
    Append-only evaluation record produced by the motor.
    Never overwritten — each evaluate() call creates a new row.
    """

    __tablename__ = "experiment_evaluations"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=False, index=True
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # insufficient_data | collecting | inconclusive | promising | underperforming
    # | winner_candidate | completed | stopped_for_safety
    evaluation_state: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_metric: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Per-variant result dict: { variant_id: { metric_value, confidence, relative_diff, ... } }
    per_variant_result: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # Aggregate confidence score [0, 1] across variants
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # { start: date, end: date, active_days: int }
    data_window: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # Date through which snapshots are considered matured
    matured_through: Mapped[date | None] = mapped_column(Date, nullable=True)
    # List of limitation strings (peeking, small sample, attribution delay, etc.)
    limitations: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    # Snapshot counts used
    total_snapshots_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # EXPLORATORY experiments never attribute causality
    causal_attribution: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    experiment: Mapped[Experiment] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Experiment", back_populates="evaluations"
    )
    decisions: Mapped[list[OptimizationDecision]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "OptimizationDecision", back_populates="evaluation"
    )
