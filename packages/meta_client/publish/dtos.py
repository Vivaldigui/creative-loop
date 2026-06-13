"""
Pydantic DTOs for Meta Marketing API publish payloads.

Rules enforced at model level:
- campaign/adset/ad status is always PAUSED — field is read-only.
- Fields that depend on user configuration can be None (serialised as placeholders).
- No invented IDs — simulated IDs exist only in SimulatedPublishResponse.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Campaign objectives supported in the Meta Marketing API ──────────────────

VALID_OBJECTIVES = {
    "OUTCOME_TRAFFIC",
    "OUTCOME_AWARENESS",
    "OUTCOME_ENGAGEMENT",
    "OUTCOME_LEADS",
    "OUTCOME_APP_PROMOTION",
    "OUTCOME_SALES",
}

VALID_BUYING_TYPES = {"AUCTION", "RESERVED"}

VALID_OPTIMIZATION_GOALS = {
    "LINK_CLICKS",
    "IMPRESSIONS",
    "REACH",
    "LANDING_PAGE_VIEWS",
    "LEAD_GENERATION",
    "CONVERSIONS",
    "APP_INSTALLS",
    "QUALITY_LEAD",
    "VALUE",
    "OFFSITE_CONVERSIONS",
    "THRUPLAY",
    "PAGE_LIKES",
    "POST_ENGAGEMENT",
}

VALID_BILLING_EVENTS = {
    "IMPRESSIONS",
    "LINK_CLICKS",
    "APP_INSTALLS",
    "PAGE_LIKES",
    "POST_ENGAGEMENT",
    "VIDEO_VIEWS",
    "THRUPLAY",
    "PURCHASE",
    "LISTING_INTERACTION",
}

VALID_BID_STRATEGIES = {
    "LOWEST_COST_WITHOUT_CAP",
    "LOWEST_COST_WITH_BID_CAP",
    "COST_CAP",
    "MINIMUM_ROAS",
}

VALID_CTA_TYPES = {
    "SHOP_NOW",
    "LEARN_MORE",
    "SIGN_UP",
    "CONTACT_US",
    "GET_OFFER",
    "BOOK_TRAVEL",
    "DOWNLOAD",
    "WATCH_MORE",
    "APPLY_NOW",
    "GET_QUOTE",
    "SUBSCRIBE",
    "INSTALL_MOBILE_APP",
    "NO_BUTTON",
}

VALID_PLACEMENTS = {
    "facebook_feed",
    "facebook_reels",
    "facebook_stories",
    "instagram_feed",
    "instagram_reels",
    "instagram_stories",
    "instagram_explore",
    "audience_network_native",
    "messenger_inbox",
}

VALID_CUSTOM_EVENT_TYPES = {
    "PURCHASE",
    "ADD_TO_CART",
    "INITIATE_CHECKOUT",
    "LEAD",
    "COMPLETE_REGISTRATION",
    "VIEW_CONTENT",
    "SEARCH",
    "ADD_TO_WISHLIST",
    "ADD_PAYMENT_INFO",
}


# ── Targeting ─────────────────────────────────────────────────────────────────

class GeoLocation(BaseModel):
    countries: list[str] = Field(default_factory=lambda: ["BR"])
    cities: list[dict[str, Any]] = Field(default_factory=list)
    regions: list[dict[str, Any]] = Field(default_factory=list)


class Targeting(BaseModel):
    geo_locations: GeoLocation = Field(default_factory=GeoLocation)
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: list[int] | None = None  # 1=male, 2=female; None=all
    flexible_spec: list[dict[str, Any]] = Field(default_factory=list)
    excluded_connections: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def age_range_valid(self) -> Targeting:
        if self.age_max < self.age_min:
            raise ValueError("age_max must be >= age_min")
        return self


# ── Promoted object (for conversion campaigns) ────────────────────────────────

class PromotedObject(BaseModel):
    pixel_id: str | None = None
    custom_event_type: str | None = None

    @field_validator("custom_event_type")
    @classmethod
    def validate_event(cls, v: str | None) -> str | None:
        if v and v not in VALID_CUSTOM_EVENT_TYPES:
            raise ValueError(f"Unknown custom_event_type: {v}")
        return v


# ── CallToAction ──────────────────────────────────────────────────────────────

class CtaValue(BaseModel):
    link: str  # landing URL


class CallToAction(BaseModel):
    type: str = "SHOP_NOW"
    value: CtaValue | None = None

    @field_validator("type")
    @classmethod
    def validate_cta_type(cls, v: str) -> str:
        if v not in VALID_CTA_TYPES:
            raise ValueError(f"Unknown CTA type: {v}")
        return v


# ── Link data (inside object_story_spec) ─────────────────────────────────────

class LinkData(BaseModel):
    image_hash: str  # PENDING_META_IMAGE_HASH in DRY_RUN
    message: str | None = None       # body text
    name: str | None = None          # headline
    description: str | None = None
    call_to_action: CallToAction | None = None
    link: str | None = None          # landing URL


# ── object_story_spec ─────────────────────────────────────────────────────────

class ObjectStorySpec(BaseModel):
    page_id: str                     # PENDING_META_PAGE_ID in DRY_RUN
    instagram_actor_id: str | None = None
    link_data: LinkData


# ── Individual payload DTOs ───────────────────────────────────────────────────

class CampaignPayload(BaseModel):
    """
    Payload for POST /{ad_account_id}/campaigns.
    status is ALWAYS PAUSED — cannot be overridden by callers.
    """
    name: str
    objective: str = "OUTCOME_TRAFFIC"
    status: str = Field(default="PAUSED", frozen=True)
    special_ad_categories: list[str] = Field(default_factory=list)
    buying_type: str = "AUCTION"

    @field_validator("status", mode="before")
    @classmethod
    def _force_paused(cls, v: str) -> str:
        return "PAUSED"

    @field_validator("objective")
    @classmethod
    def validate_objective(cls, v: str) -> str:
        if v not in VALID_OBJECTIVES:
            raise ValueError(f"Unknown objective: {v}. Valid: {sorted(VALID_OBJECTIVES)}")
        return v

    @field_validator("buying_type")
    @classmethod
    def validate_buying_type(cls, v: str) -> str:
        if v not in VALID_BUYING_TYPES:
            raise ValueError(f"Unknown buying_type: {v}")
        return v


class AdSetPayload(BaseModel):
    """
    Payload for POST /{ad_account_id}/adsets.
    status is ALWAYS PAUSED.
    daily_budget must be in the account currency's smallest unit (e.g. centavos for BRL).
    """
    name: str
    campaign_id: str  # simulated or real campaign ID
    daily_budget: int = Field(ge=1, description="In smallest currency unit (e.g. centavos)")
    billing_event: str = "IMPRESSIONS"
    optimization_goal: str = "LINK_CLICKS"
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP"
    targeting: Targeting = Field(default_factory=Targeting)
    promoted_object: PromotedObject | None = None
    start_time: str | None = None   # ISO 8601; None = start immediately
    status: str = Field(default="PAUSED", frozen=True)

    @field_validator("status", mode="before")
    @classmethod
    def _force_paused(cls, v: str) -> str:
        return "PAUSED"

    @field_validator("billing_event")
    @classmethod
    def validate_billing(cls, v: str) -> str:
        if v not in VALID_BILLING_EVENTS:
            raise ValueError(f"Unknown billing_event: {v}")
        return v

    @field_validator("optimization_goal")
    @classmethod
    def validate_opt_goal(cls, v: str) -> str:
        if v not in VALID_OPTIMIZATION_GOALS:
            raise ValueError(f"Unknown optimization_goal: {v}")
        return v

    @field_validator("bid_strategy")
    @classmethod
    def validate_bid(cls, v: str) -> str:
        if v not in VALID_BID_STRATEGIES:
            raise ValueError(f"Unknown bid_strategy: {v}")
        return v


class ImageUploadPayload(BaseModel):
    """
    Represents what would be sent to POST /{ad_account_id}/adimages.
    In DRY_RUN, no upload happens; the simulated hash is stored.
    """
    source_storage_key: str         # internal storage key
    image_hash: str                 # sha256 already computed
    bytes_len: int
    filename: str
    # The hash Meta would return — always PENDING_META_IMAGE_HASH in DRY_RUN
    placeholder_image_hash: str = "PENDING_META_IMAGE_HASH_AFTER_UPLOAD"


class AdCreativePayload(BaseModel):
    """
    Payload for POST /{ad_account_id}/adcreatives.
    object_story_spec.page_id filled with PENDING_META_PAGE_ID if not configured.
    """
    name: str
    object_story_spec: ObjectStorySpec
    degrees_of_freedom_spec: dict[str, Any] | None = None


class AdPayload(BaseModel):
    """
    Payload for POST /{ad_account_id}/ads.
    status is ALWAYS PAUSED.
    """
    name: str
    adset_id: str       # simulated or real ad set ID
    creative: dict[str, str]  # {"creative_id": "<id>"}
    status: str = Field(default="PAUSED", frozen=True)
    tracking_specs: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def _force_paused(cls, v: str) -> str:
        return "PAUSED"


# ── Root payload aggregating all five steps ───────────────────────────────────

class MetaPublishPayload(BaseModel):
    """
    Complete publish specification.
    All five sub-payloads plus metadata required by the Graph API.
    """
    graph_api_version: str = "v21.0"
    ad_account_id: str              # e.g. "act_NNNN" or PENDING_META_AD_ACCOUNT_ID
    page_id: str                    # Meta Page ID or PENDING_META_PAGE_ID
    instagram_actor_id: str | None = None
    pixel_id: str | None = None
    optimization_event: str | None = None  # PURCHASE / LEAD / etc.
    placements: list[str] = Field(default_factory=lambda: ["facebook_feed", "instagram_feed"])
    url: str | None = None           # landing page URL
    tracking_params: dict[str, str] = Field(default_factory=dict)

    campaign: CampaignPayload
    adset: AdSetPayload
    image_upload: ImageUploadPayload
    ad_creative: AdCreativePayload
    ad: AdPayload

    @field_validator("placements")
    @classmethod
    def validate_placements(cls, v: list[str]) -> list[str]:
        invalid = [p for p in v if p not in VALID_PLACEMENTS]
        if invalid:
            raise ValueError(f"Unknown placements: {invalid}")
        return v


# ── Simulated response ────────────────────────────────────────────────────────

class SimulatedPublishResponse(BaseModel):
    """
    Response returned by DryRunPublisher.
    All IDs are clearly prefixed 'simulated_' — never real Meta IDs.
    """
    dry_run: bool = True
    mode: str = "DRY_RUN"
    note: str = "DRY_RUN=true — zero write calls to Meta. No campaign was created."

    simulated_campaign_id: str
    simulated_adset_id: str
    simulated_image_hash: str
    simulated_ad_creative_id: str
    simulated_ad_id: str

    steps_simulated: list[str] = Field(default_factory=list)
    placeholders_present: list[str] = Field(default_factory=list)
