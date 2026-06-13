"""Pydantic schemas for experiments, variants, evaluations, decisions and metrics."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

# ── Variant schemas ────────────────────────────────────────────────────────────

class VariantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str | None = None
    is_control: bool = False
    variant_role: str = "test"
    creative_id: uuid.UUID | None = None
    prompt_version_id: uuid.UUID | None = None
    published_ad_id: uuid.UUID | None = None
    changed_variables: list[str] | None = None
    allocated_budget: float | None = None
    audience: dict[str, Any] | None = None
    metadata_: dict[str, Any] | None = None


class VariantOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    name: str
    hypothesis: str | None
    is_control: bool
    variant_role: str
    status: str
    creative_id: uuid.UUID | None
    prompt_version_id: uuid.UUID | None
    published_ad_id: uuid.UUID | None
    changed_variables: list[str] | None
    allocated_budget: float | None
    is_fictitious: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Experiment schemas ─────────────────────────────────────────────────────────

class MinCriteriaIn(BaseModel):
    min_spend: float | None = None
    min_impressions: int | None = None
    min_clicks: int | None = None
    min_conversions: int | None = None
    min_days: int | None = None
    min_difference: float | None = None
    min_confidence: float | None = None
    max_frequency: float | None = None
    maturation_window_days: int | None = None


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    mode: str = Field(default="CONTROLLED", pattern="^(CONTROLLED|EXPLORATORY)$")
    hypothesis: str | None = None
    primary_variable: str | None = None
    objective: str | None = None
    product_id: uuid.UUID | None = None
    audience: dict[str, Any] | None = None
    placement: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    planned_budget: float | None = None
    currency: str | None = None
    primary_metric: str | None = None
    secondary_metrics: list[str] | None = None
    min_criteria: MinCriteriaIn | None = None
    variants: list[VariantCreate] | None = None
    is_fictitious: bool = False

    @model_validator(mode="after")
    def controlled_requires_primary_variable(self) -> ExperimentCreate:
        if self.mode == "CONTROLLED" and not self.primary_variable:
            raise ValueError("CONTROLLED experiments require primary_variable.")
        return self


class ExperimentUpdate(BaseModel):
    name: str | None = None
    hypothesis: str | None = None
    primary_variable: str | None = None
    objective: str | None = None
    audience: dict[str, Any] | None = None
    placement: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    planned_budget: float | None = None
    primary_metric: str | None = None
    secondary_metrics: list[str] | None = None
    min_criteria: MinCriteriaIn | None = None


class ExperimentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    mode: str
    hypothesis: str | None
    primary_variable: str | None
    status: str
    evaluation_state: str | None
    objective: str | None
    product_id: uuid.UUID | None
    audience: dict[str, Any] | None
    placement: str | None
    window_start: date | None
    window_end: date | None
    planned_budget: float | None
    currency: str | None
    primary_metric: str | None
    secondary_metrics: list[str] | None
    min_criteria: dict[str, Any] | None
    stop_reason: str | None
    started_at: datetime | None
    ended_at: datetime | None
    is_fictitious: bool
    created_at: datetime
    updated_at: datetime
    variants: list[VariantOut] = []

    model_config = {"from_attributes": True}


class ExperimentStartRequest(BaseModel):
    confirm: bool = Field(default=False, description="Must be True to start")


class ExperimentStopRequest(BaseModel):
    stop_reason: str = Field(default="manual")
    notes: str | None = None


# ── Evaluation schemas ─────────────────────────────────────────────────────────

class EvaluationRequest(BaseModel):
    notes: str | None = None


class VariantResultOut(BaseModel):
    variant_id: str
    is_control: bool
    metric_value: float | None
    relative_diff: float | None
    confidence: float | None
    aggregated: dict[str, Any] = {}


class EvaluationOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    evaluated_at: datetime
    evaluation_state: str
    primary_metric: str | None
    per_variant_result: dict[str, Any] | None
    confidence: float | None
    data_window: dict[str, Any] | None
    matured_through: date | None
    limitations: list[str] | None
    total_snapshots_used: int | None
    engine_version: str
    causal_attribution: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Decision schemas ───────────────────────────────────────────────────────────

class DecisionCreate(BaseModel):
    evaluation_id: uuid.UUID | None = None
    primary_metric: str | None = None
    recommendation: str | None = None
    # continue | pause | review | create_new_hypothesis | wait_more_data
    suggested_action: str | None = None
    executed_action: str | None = None
    execution_notes: str | None = None


class DecisionOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    evaluation_id: uuid.UUID | None
    data_used: dict[str, Any] | None
    period_start: str | None
    period_end: str | None
    primary_metric: str | None
    result: dict[str, Any] | None
    confidence: float | None
    limitations: list[str] | None
    recommendation: str | None
    suggested_action: str | None
    executed_action: str | None
    execution_notes: str | None
    user_responsible_id: uuid.UUID | None
    decided_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Metric snapshot schemas ────────────────────────────────────────────────────

class VariantSnapshotOut(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    variant_id: uuid.UUID
    date_start: str | None
    date_stop: str | None
    impressions: int | None
    reach: int | None
    frequency: float | None
    spend: float | None
    clicks: int | None
    link_clicks: int | None
    ctr: float | None
    cpc: float | None
    cpm: float | None
    landing_page_views: int | None
    adds_to_cart: int | None
    initiate_checkout: int | None
    purchases: int | None
    leads: int | None
    cost_per_result: float | None
    purchase_value: float | None
    roas: float | None
    is_matured: bool
    is_fictitious: bool
    attribution_window: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
