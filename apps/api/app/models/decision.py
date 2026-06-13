from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class OptimizationDecision(Base, UUIDMixin, OrgMixin, TimestampMixin):
    """
    Human-triggered optimization decision linked to an evaluation.

    v1 — only suggests; executed_action requires human actor.
    Budget is never changed automatically (max_automatic_budget_increase_percent=0).
    """

    __tablename__ = "optimization_decisions"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=False, index=True
    )
    evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiment_evaluations.id"), nullable=True, index=True
    )

    # Snapshot of data context used for this decision
    data_used: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    period_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    period_end: Mapped[str | None] = mapped_column(String(20), nullable=True)

    primary_metric: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    limitations: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # continue | pause | review | create_new_hypothesis | wait_more_data
    suggested_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Filled only when a human explicitly executes an action
    executed_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    execution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_responsible_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_log_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)

    experiment: Mapped[Experiment] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Experiment", back_populates="decisions"
    )
    evaluation: Mapped[ExperimentEvaluation | None] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExperimentEvaluation", back_populates="decisions"
    )
