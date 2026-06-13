from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class Learning(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """
    Structured learning extracted from an experiment evaluation.

    Lifecycle: provisional → confirmed  (requires human review + corroboration)
               provisional → rejected   (requires comment with counter-evidence)

    No single learning is treated as definitive truth.
    """

    __tablename__ = "learnings"

    # Descriptive context
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("products.id"), nullable=True, index=True
    )
    audience: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    placement: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Core learning content
    observed_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    limitations: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Traceability
    source_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=True, index=True
    )
    source_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiment_evaluations.id"), nullable=True
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Status lifecycle
    # provisional | confirmed | rejected
    status: Mapped[str] = mapped_column(String(20), default="provisional", nullable=False, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # agent | user
    responsible_type: Mapped[str] = mapped_column(String(20), default="agent", nullable=False)

    # Semantic embedding stored as JSON list[float] (pgvector in production)
    embedding: Mapped[list[float] | None] = mapped_column(JSONBType, nullable=True)

    # Self-reference: when this learning supersedes an older one
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("learnings.id"), nullable=True
    )
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    usages: Mapped[list[LearningUsage]] = relationship(
        "LearningUsage", back_populates="learning"
    )


class LearningUsage(Base, UUIDMixin, OrgMixin, TimestampMixin):
    """Tracks each time a Learning was used to generate a hypothesis / prompt."""

    __tablename__ = "learning_usages"

    learning_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("learnings.id"), nullable=False, index=True
    )
    # Either suggestion_id or prompt_version_id (or both) will be set
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiment_suggestions.id"), nullable=True, index=True
    )
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("prompt_versions.id"), nullable=True
    )
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    learning: Mapped[Learning] = relationship("Learning", back_populates="usages")
