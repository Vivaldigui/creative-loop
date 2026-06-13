from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class Approval(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "approvals"

    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    # approve | reject | request_variation
    action: Mapped[str] = mapped_column(String(30), nullable=False, default="approve")
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved | rejected
    decided_by: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Snapshot of what was approved — immutable record
    snapshot_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_copy: Mapped[str | None] = mapped_column(Text, nullable=True)
    # IDs of QualityCheck/PolicyCheck records that were overridden (owner only)
    overridden_check_ids: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)

    creative: Mapped[GeneratedCreative] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", back_populates="approvals"
    )
