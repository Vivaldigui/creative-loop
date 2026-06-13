from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class CreativeHypothesis(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """
    A testable hypothesis derived from a CreativeAnalysis.
    Links source ad → analysis → hypothesis → PromptTemplate.
    """

    __tablename__ = "creative_hypotheses"

    source_ad_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("source_ads.id"), nullable=False, index=True
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("creative_analyses.id"), nullable=False, index=True
    )

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_variable: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_effect: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | selected | promoted
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    source_ad: Mapped[SourceAd] = relationship("SourceAd")  # type: ignore[name-defined]  # noqa: F821
    analysis: Mapped[CreativeAnalysis] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CreativeAnalysis", back_populates="hypotheses"
    )
    prompt_templates: Mapped[list[PromptTemplate]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "PromptTemplate", back_populates="hypothesis"
    )
