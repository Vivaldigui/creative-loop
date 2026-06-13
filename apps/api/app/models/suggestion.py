from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class ExperimentSuggestion(Base, UUIDMixin, OrgMixin, TimestampMixin):
    """
    AI-generated suggestion for a next experiment round.

    v1 safety contract:
    - Never generates images automatically (guard_no_auto_image_generation).
    - Never publishes automatically (guard_no_auto_publish).
    - Human approval required before any downstream generation/publication.
    """

    __tablename__ = "experiment_suggestions"

    source_experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=False, index=True
    )
    # Draft experiment created for this suggestion (null until approved and instantiated)
    draft_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=True
    )
    # Draft prompt version created for this suggestion
    draft_prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("prompt_versions.id"), nullable=True
    )

    # Learning IDs used to build this suggestion
    selected_learning_ids: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)

    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_variable: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Score from DiversityScorer [0,1]; higher = more diverse from existing work
    diversity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # pending_approval | approved | rejected
    status: Mapped[str] = mapped_column(String(30), default="pending_approval", nullable=False, index=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audit_log_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)

    # Full context snapshot at generation time
    context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    source_experiment: Mapped[Experiment] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Experiment",
        foreign_keys=[source_experiment_id],
    )
