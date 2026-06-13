"""
Anthropic client interface and Pydantic schemas.

AnalysisResult separates four knowledge kinds:
- observations   : what was directly seen visually
- metric_facts   : facts derived from ad performance metrics
- performance_hypotheses : unproven speculations
- limitations    : what could NOT be concluded (unknown, insufficient data)
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Sub-schemas ───────────────────────────────────────────────────

class Observation(BaseModel):
    """A visual observation (category = what was seen)."""
    text: str
    category: Literal[
        "composition", "color", "text", "product", "attention", "style", "other"
    ] = "other"

    model_config = ConfigDict(extra="ignore")


class MetricFact(BaseModel):
    """A fact derived from the ad's performance metrics (not visual inference)."""
    text: str
    metric: str | None = None
    value: float | None = None

    model_config = ConfigDict(extra="ignore")


class PerformanceHypothesis(BaseModel):
    """An unproven speculation linking a visual element to performance."""
    statement: str
    primary_variable: str | None = None
    expected_effect: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="ignore")


class CompositionInfo(BaseModel):
    layout: str | None = None
    thirds_rule: bool | None = None
    focal_point: str | None = None
    note: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class HierarchyInfo(BaseModel):
    primary_element: str | None = None
    secondary_element: str | None = None
    cta_position: str | None = None
    note: str | None = None

    model_config = ConfigDict(extra="allow")


class ProductPresentation(BaseModel):
    angle: str | None = None
    context: str | None = None
    note: str | None = None

    model_config = ConfigDict(extra="allow")


class ColorLighting(BaseModel):
    dominant_colors: list[str] = Field(default_factory=list)
    lighting: str | None = None
    note: str | None = None

    model_config = ConfigDict(extra="allow")


class TextAnalysis(BaseModel):
    word_count: int | None = None
    headline_present: bool | None = None
    cta_present: bool | None = None
    note: str | None = None

    model_config = ConfigDict(extra="allow")


# ── Main schema ───────────────────────────────────────────────────

class AnalysisResult(BaseModel):
    """
    Structured creative analysis returned by the provider.

    Fields are segregated by epistemological kind:
    - observations / composition / hierarchy / product_presentation /
      color_and_lighting / text_analysis / attention_elements →  visual observation
    - metric_facts → derived from performance metrics
    - performance_hypotheses → unproven speculation
    - limitations → what remains unknown or unconfirmed
    - strengths / weaknesses → summary judgements
    """

    # top-level free-text summary
    visual_summary: str = ""

    # Phase 3 segregated fields
    observations: list[Observation] = Field(default_factory=list)
    metric_facts: list[MetricFact] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # Structured visual breakdown
    composition: CompositionInfo = Field(default_factory=CompositionInfo)
    hierarchy: HierarchyInfo = Field(default_factory=HierarchyInfo)
    product_presentation: ProductPresentation = Field(default_factory=ProductPresentation)
    color_and_lighting: ColorLighting = Field(default_factory=ColorLighting)
    text_analysis: TextAnalysis = Field(default_factory=TextAnalysis)

    attention_elements: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    performance_hypotheses: list[PerformanceHypothesis] = Field(default_factory=list)
    elements_to_preserve: list[str] = Field(default_factory=list)
    elements_to_test: list[str] = Field(default_factory=list)
    policy_risks: list[str] = Field(default_factory=list)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="ignore")

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, fv))

    def to_storage_dict(self) -> dict[str, Any]:
        """Return a plain dict safe for JSONB storage (uses model_dump, no Pydantic objects)."""
        return self.model_dump()


# ── Request ───────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    ad_name: str
    headline: str | None = None
    body_text: str | None = None
    cta: str | None = None
    image_path: str | None = None
    image_url: str | None = None
    product_name: str | None = None
    brand_name: str | None = None
    segment: str | None = None
    audience: str | None = None
    placement: str | None = None
    objective: str | None = None
    date_range: str | None = None
    metrics: dict[str, Any] | None = None
    landing_page_url: str | None = None

    model_config = ConfigDict(extra="ignore")


# ── Envelope ─────────────────────────────────────────────────────

class UsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int


class AnalysisEnvelope(BaseModel):
    """Wraps AnalysisResult with call metadata (tokens, cost, latency, status)."""
    result: AnalysisResult
    model_used: str
    usage: UsageInfo | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int = 0
    status: Literal["completed", "partial", "failed"] = "completed"
    repaired: bool = False
    error_detail: str | None = None


# ── Protocol ─────────────────────────────────────────────────────

class AnthropicClientProtocol(Protocol):
    async def analyze(
        self,
        request: AnalysisRequest,
        *,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> AnalysisEnvelope: ...

    async def health_check(self) -> bool: ...
