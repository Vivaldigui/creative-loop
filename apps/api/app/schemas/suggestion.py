"""Pydantic schemas for experiment suggestions (next round)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SuggestionOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    source_experiment_id: uuid.UUID
    draft_experiment_id: uuid.UUID | None
    draft_prompt_version_id: uuid.UUID | None
    selected_learning_ids: list[str] | None
    hypothesis: str | None
    primary_variable: str | None
    rationale: str | None
    diversity_score: float | None
    status: str
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_comment: str | None
    context_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SuggestionReviewRequest(BaseModel):
    comment: str | None = None
