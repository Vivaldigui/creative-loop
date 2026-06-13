"""Pydantic schemas for learnings and learning usages."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class LearningCreate(BaseModel):
    context: str | None = None
    segment: str | None = None
    product_id: uuid.UUID | None = None
    audience: dict[str, Any] | None = None
    placement: str | None = None
    format: str | None = None
    objective: str | None = None
    observed_pattern: str = Field(min_length=1)
    evidence: dict[str, Any] | None = None
    sample_size: int | None = None
    metrics: dict[str, Any] | None = None
    limitations: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_experiment_id: uuid.UUID | None = None
    source_evaluation_id: uuid.UUID | None = None
    period_start: date | None = None
    period_end: date | None = None
    responsible_type: str = "agent"
    supersedes_id: uuid.UUID | None = None
    is_fictitious: bool = False


class LearningReviewRequest(BaseModel):
    comment: str | None = None


class LearningRejectRequest(BaseModel):
    comment: str = Field(min_length=1, description="Counter-evidence or reason for rejection required.")


class LearningOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    context: str | None
    segment: str | None
    product_id: uuid.UUID | None
    audience: dict[str, Any] | None
    placement: str | None
    format: str | None
    objective: str | None
    observed_pattern: str
    evidence: dict[str, Any] | None
    sample_size: int | None
    metrics: dict[str, Any] | None
    limitations: list[str] | None
    confidence: float | None
    source_experiment_id: uuid.UUID | None
    source_evaluation_id: uuid.UUID | None
    period_start: date | None
    period_end: date | None
    status: str
    reviewed_at: datetime | None
    reviewed_by_id: uuid.UUID | None
    review_comment: str | None
    responsible_type: str
    supersedes_id: uuid.UUID | None
    is_fictitious: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
