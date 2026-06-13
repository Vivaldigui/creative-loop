from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class CreativeAnalysis(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Structured visual analysis produced by Claude (or mock)."""

    __tablename__ = "creative_analyses"

    source_ad_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("source_ads.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # pending | completed | failed | partial
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)

    # Phase 3 — deduplication / versioning
    # sha256(model+image_hash+metrics_json+request_fields) for idempotency
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # incremental version for the same (org, source_ad); append-only
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # image | video | carousel | none
    media_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Structured output validated by Pydantic (stored as JSON)
    visual_summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Phase 3 new typed lists
    observations: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    metric_facts: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    limitations: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # Original fields
    composition: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    hierarchy: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    product_presentation: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    color_and_lighting: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    text_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    attention_elements: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    strengths: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    weaknesses: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    performance_hypotheses: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    elements_to_preserve: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    elements_to_test: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    policy_risks: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Phase 3 — request metadata (no secrets, no image content)
    request_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repaired: Mapped[bool] = mapped_column(default=False, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_ad: Mapped[SourceAd] = relationship("SourceAd", back_populates="analyses")  # type: ignore[name-defined]  # noqa: F821
    prompt_versions: Mapped[list[PromptVersion]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "PromptVersion", back_populates="analysis"
    )
    hypotheses: Mapped[list[CreativeHypothesis]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CreativeHypothesis", back_populates="analysis"
    )
