from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class PublicationDraft(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """
    Editable pre-simulation configuration.
    Holds assembled payload + hash before a dry-run is requested.
    """

    __tablename__ = "publication_drafts"

    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("experiments.id"), nullable=True, index=True
    )

    # User-supplied configs (raw form input)
    campaign_config: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    adset_config: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    ad_config: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    landing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracking_params: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    # Assembled MetaPublishPayload (serialised dict) + its canonical hash
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # draft | validated | simulated | invalid
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    creative: Mapped[GeneratedCreative] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", foreign_keys=[creative_id]
    )
    attempts: Mapped[list[PublicationAttempt]] = relationship(
        "PublicationAttempt", back_populates="draft"
    )


class PublicationAttempt(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """
    Immutable record of one dry-run attempt.
    Written once; never updated (result is final after creation).
    """

    __tablename__ = "publication_attempts"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_attempt_org_idem_key"),
    )

    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("publication_drafts.id"), nullable=True, index=True
    )
    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # DRY_RUN or REAL
    mode: Mapped[str] = mapped_column(String(20), default="DRY_RUN", nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Structured list of CheckResult dicts
    checks: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    # Simulated IDs (DRY_RUN) or real IDs (REAL) — clearly marked per mode
    simulated_response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    # simulated | rejected | conflict | error | published | partial | requires_manual_review | failed
    result: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 6: x-fb-request-id per step {step_name: request_id}
    meta_request_ids: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    published_ad_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("published_ads.id"), nullable=True
    )

    draft: Mapped[PublicationDraft | None] = relationship(
        "PublicationDraft", back_populates="attempts"
    )
    steps: Mapped[list[PublicationStep]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "PublicationStep", back_populates="attempt"
    )
