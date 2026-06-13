from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType

CHECK_RESULT_PASS = "PASS"
CHECK_RESULT_WARNING = "WARNING"
CHECK_RESULT_BLOCKED = "BLOCKED"


class QualityCheck(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "quality_checks"

    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # PASS | WARNING | BLOCKED
    findings: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    override_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    creative: Mapped[GeneratedCreative] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", back_populates="quality_checks"
    )


class PolicyCheck(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "policy_checks"

    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # PASS | WARNING | BLOCKED
    findings: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    rule_set_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_by: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    creative: Mapped[GeneratedCreative] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", back_populates="policy_checks"
    )
