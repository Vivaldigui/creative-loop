from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class PublishedAd(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """Record of a publish attempt (DRY_RUN or real). Real ads always start PAUSED."""

    __tablename__ = "published_ads"

    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    dry_run: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Payload that was / would have been sent to Meta
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    # External IDs assigned by Meta (null in DRY_RUN)
    meta_campaign_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_adset_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_ad_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_creative_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_image_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Configured status — always PAUSED after creation; only changes via manual activation
    status: Mapped[str] = mapped_column(String(50), default="dry_run", nullable=False)

    # Phase 6: effective_status from Meta (may differ from configured_status during review)
    effective_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Phase 6: workflow state machine (see PublicationStep.state values)
    workflow_state: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Phase 6: timestamps for lifecycle events
    last_status_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)

    # Phase 6: rejection info
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 6: tag injected into Meta resource names for reconciliation
    idempotency_tag: Mapped[str | None] = mapped_column(String(200), nullable=True)

    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    creative: Mapped[GeneratedCreative] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", back_populates="published_ads"
    )


class PublicationStep(Base, UUIDMixin, OrgMixin, TimestampMixin):
    """
    One step in the real publish workflow.

    State machine values (in order):
        validated → image_uploaded → campaign_resolved → adset_resolved
        → creative_created → ad_created_paused → status_checked → completed
        (error branches) → failed | requires_manual_review
    """

    __tablename__ = "publication_steps"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("publication_attempts.id"), nullable=False, index=True
    )

    # The state this step represents
    state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Meta node created or resolved in this step (null if step failed)
    meta_node_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # x-fb-request-id from the Meta API response for this step
    meta_request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Error info (if failed)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether the error is recoverable (can resume from this step)
    is_recoverable: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Serialised request/response (sanitised — no tokens)
    step_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)

    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt: Mapped[PublicationAttempt] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "PublicationAttempt", back_populates="steps"
    )
