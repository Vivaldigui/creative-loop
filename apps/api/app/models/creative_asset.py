from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType

ASSET_ROLES = {"original", "derivative", "thumbnail"}
FIT_STRATEGIES = {"none", "pad", "crop"}


class CreativeAsset(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    """
    A stored image file linked to a GeneratedCreative.

    Each creative has one "original" asset and zero-or-more "derivative" assets
    (resized for different ad formats) plus a "thumbnail".
    """

    __tablename__ = "creative_assets"

    creative_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("generated_creatives.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # original | derivative | thumbnail
    format_label: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # "1080x1080" | "1080x1350" | "1080x1920" | "thumb"

    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), nullable=False, default="local")

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fit_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)  # none | pad | crop

    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    creative: Mapped[GeneratedCreative] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "GeneratedCreative", back_populates="assets"
    )
