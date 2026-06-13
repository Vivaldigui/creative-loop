from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, JSONBType, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin


class IntegrationCredential(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "integration_credentials"

    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # meta | anthropic | openai
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # All secrets stored encrypted via Fernet; never in plaintext
    encrypted_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    last_verified_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Phase 6 — token lifecycle
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    last_health_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
