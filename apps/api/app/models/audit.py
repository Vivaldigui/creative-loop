from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, JSONBType, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class AuditLog(Base, UUIDMixin, OrgMixin, TimestampMixin):
    """Immutable audit record. Written before any sensitive action, then updated with result."""

    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    result: Mapped[str | None] = mapped_column(String(50), nullable=True)  # success | error | dry_run
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Phase 5 — publish traceability
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    limits_checked: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    # Phase 6 — emergency pause flag
    emergency: Mapped[bool] = mapped_column(default=False, nullable=False)
