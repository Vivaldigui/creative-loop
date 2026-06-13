from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class PromptTemplate(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("products.id"), nullable=True, index=True
    )
    # Phase 3 — link to originating hypothesis
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("creative_hypotheses.id"), nullable=True, index=True
    )
    ad_format: Mapped[str | None] = mapped_column(String(50), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    versions: Mapped[list[PromptVersion]] = relationship(
        "PromptVersion", back_populates="template", order_by="PromptVersion.version_number"
    )
    hypothesis: Mapped[CreativeHypothesis | None] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CreativeHypothesis", back_populates="prompt_templates"
    )


class PromptVersion(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Immutable versioned prompt. Never overwrite — always create a new version."""

    __tablename__ = "prompt_versions"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("prompt_templates.id"), nullable=False, index=True
    )
    source_ad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("source_ads.id"), nullable=True, index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("creative_analyses.id"), nullable=True, index=True
    )
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("prompt_versions.id"), nullable=True
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Full prompt text as sent to the image model
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured fields for UI display and auditability
    structured_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # Human-readable unified diff vs. parent version
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_used: Mapped[str | None] = mapped_column(Text, nullable=True)

    author_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    # Phase 3 — human | agent
    author_type: Mapped[str] = mapped_column(String(20), default="human", nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # sha256(prompt_text) — used for identical-revision detection
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Target image model (informational; generation is Phase 4)
    target_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # draft | active | archived
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    template: Mapped[PromptTemplate] = relationship("PromptTemplate", back_populates="versions")
    analysis: Mapped[CreativeAnalysis | None] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CreativeAnalysis", back_populates="prompt_versions"
    )
    generated_creatives: Mapped[list[GeneratedCreative]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", back_populates="prompt_version"
    )
