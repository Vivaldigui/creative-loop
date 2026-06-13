"""Request/response Pydantic schemas for the publish endpoints."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class DryRunRequest(BaseModel):
    creative_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=200)

    # Campaign
    campaign_name: str | None = None
    objective: str = "OUTCOME_TRAFFIC"

    # Ad set
    adset_name: str | None = None
    daily_budget_brl: float = Field(gt=0, description="Daily budget in BRL (main unit, not centavos)")
    optimization_goal: str = "LINK_CLICKS"
    billing_event: str = "IMPRESSIONS"
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP"
    targeting: dict[str, Any] | None = None
    promoted_object: dict[str, Any] | None = None
    placements: list[str] | None = None

    # Ad
    ad_name: str | None = None
    headline: str | None = None
    body_text: str | None = None
    cta_type: str = "SHOP_NOW"

    # Landing page + tracking
    landing_url: str | None = None
    tracking_params: dict[str, str] | None = None

    # Optional experiment linkage
    experiment_id: uuid.UUID | None = None

    # Optional draft linkage
    draft_id: uuid.UUID | None = None


class ValidateRequest(BaseModel):
    creative_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=200, default="validate_check")
    objective: str = "OUTCOME_TRAFFIC"
    daily_budget_brl: float = Field(gt=0)
    optimization_goal: str = "LINK_CLICKS"
    landing_url: str | None = None
    experiment_id: uuid.UUID | None = None

    # Minimum required for payload build
    campaign_name: str | None = None
    adset_name: str | None = None
    ad_name: str | None = None
    targeting: dict[str, Any] | None = None


class DraftUpsertRequest(BaseModel):
    creative_id: uuid.UUID
    experiment_id: uuid.UUID | None = None
    campaign_config: dict[str, Any] | None = None
    adset_config: dict[str, Any] | None = None
    ad_config: dict[str, Any] | None = None
    landing_url: str | None = None
    tracking_params: dict[str, Any] | None = None


class CheckResultOut(BaseModel):
    code: str
    severity: str
    passed: bool
    detail: str = ""


class ValidateResponse(BaseModel):
    creative_id: str
    passed: bool
    blocked_count: int
    warning_count: int
    checks: list[CheckResultOut]
    payload_preview: dict[str, Any] | None = None
    dry_run_mode: bool = True


class DryRunResponse(BaseModel):
    attempt_id: str
    published_ad_id: str | None
    dry_run: bool = True
    mode: str = "DRY_RUN"
    idempotent: bool = False
    result: str
    checks: list[dict[str, Any]]
    simulated_response: dict[str, Any] | None
    payload: dict[str, Any] | None
    correlation_id: str
    message: str


class DraftOut(BaseModel):
    id: str
    creative_id: str
    experiment_id: str | None
    status: str
    payload_hash: str | None
    created_at: str
    updated_at: str


class AttemptOut(BaseModel):
    id: str
    creative_id: str
    draft_id: str | None
    idempotency_key: str
    payload_hash: str
    mode: str
    correlation_id: str | None
    result: str
    simulated_response: dict[str, Any] | None
    checks: list[dict[str, Any]] | None
    error_detail: str | None
    published_ad_id: str | None
    created_at: str


# ─── Phase 6: real publish schemas ───────────────────────────────────────────

class RealPublishRequest(BaseModel):
    """Request body for POST /publish/meta (real publish)."""
    creative_id: uuid.UUID
    idempotency_key: str = Field(min_length=1, max_length=200)

    # Campaign
    campaign_name: str | None = None
    objective: str = "OUTCOME_TRAFFIC"

    # Ad set
    adset_name: str | None = None
    daily_budget_brl: float = Field(gt=0, description="Daily budget in BRL")
    optimization_goal: str = "LINK_CLICKS"
    billing_event: str = "IMPRESSIONS"
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP"
    targeting: dict[str, Any] | None = None
    promoted_object: dict[str, Any] | None = None
    placements: list[str] | None = None

    # Ad creative
    ad_name: str | None = None
    headline: str | None = None
    body_text: str | None = None
    cta_type: str = "SHOP_NOW"

    # Landing page + tracking
    landing_url: str = Field(description="Required for real publish.")
    tracking_params: dict[str, str] | None = None

    # Optional linkage
    experiment_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None

    # Caller confirms they understand the ad is created PAUSED
    confirm_paused: bool = Field(
        default=False,
        description="Must be true to proceed. Ad will be created PAUSED and require manual activation.",
    )


class StepOut(BaseModel):
    """One step in the real publish workflow."""
    state: str
    meta_node_id: str | None = None
    meta_request_id: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    is_recoverable: bool = True
    finished_at: str | None = None


class RealPublishResponse(BaseModel):
    """Response for POST /publish/meta (real publish)."""
    attempt_id: str
    published_ad_id: str | None
    mode: str = "REAL"
    idempotent: bool = False
    result: str
    workflow_state: str | None = None
    meta_ad_id: str | None = None
    meta_campaign_id: str | None = None
    meta_adset_id: str | None = None
    meta_creative_id: str | None = None
    meta_image_hash: str | None = None
    checks: list[dict[str, Any]]
    error_detail: str | None = None
    requires_manual_review: bool = False
    correlation_id: str
    message: str


class PublishStatusResponse(BaseModel):
    """Response for GET /publication-attempts/{id}/status."""
    attempt_id: str
    published_ad_id: str | None
    mode: str
    result: str
    workflow_state: str | None = None
    meta_ad_id: str | None = None
    meta_campaign_id: str | None = None
    effective_status: str | None = None
    error_detail: str | None = None
    requires_manual_review: bool = False
    created_at: str
    steps: list[StepOut] = Field(default_factory=list)


class ActivateRequest(BaseModel):
    """Request body for POST /published-ads/{id}/activate."""
    confirmation: str = Field(
        description="Must equal the ad's meta_ad_id (or published_ad id if meta_ad_id is unknown)."
    )


class ActivateResponse(BaseModel):
    """Response for POST /published-ads/{id}/activate."""
    published_ad_id: str
    meta_ad_id: str | None = None
    status: str
    activated_at: str | None = None
    activated_by: str | None = None
    error: str | None = None
    blocked: bool = False


class PauseResponse(BaseModel):
    """Response for POST /published-ads/{id}/pause and /emergency-pause."""
    published_ad_id: str
    meta_ad_id: str | None = None
    status: str
    emergency: bool = False
    paused_at: str | None = None
    paused_by: str | None = None
    error: str | None = None


class PublishedAdOut(BaseModel):
    """Summary of a published ad record."""
    id: str
    creative_id: str
    dry_run: bool
    status: str
    effective_status: str | None = None
    workflow_state: str | None = None
    meta_ad_id: str | None = None
    meta_campaign_id: str | None = None
    meta_adset_id: str | None = None
    meta_image_hash: str | None = None
    idempotency_tag: str | None = None
    activated_at: str | None = None
    paused_at: str | None = None
    last_status_checked_at: str | None = None
    error_detail: str | None = None
    created_at: str
