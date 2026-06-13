from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, MetadataMixin, OrgMixin, TimestampMixin, UUIDMixin, UUIDType


class Product(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    is_fictitious: Mapped[bool] = mapped_column(default=False, nullable=False)

    brand_profiles: Mapped[list[BrandProfile]] = relationship(
        "BrandProfile", back_populates="product"
    )
    source_ads: Mapped[list[SourceAd]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "SourceAd", back_populates="product"
    )


class BrandProfile(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "brand_profiles"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("products.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    font_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_of_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    prohibited_elements: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    product: Mapped[Product] = relationship("Product", back_populates="brand_profiles")
    assets: Mapped[list[BrandAsset]] = relationship("BrandAsset", back_populates="brand_profile")


class BrandAsset(Base, UUIDMixin, OrgMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "brand_assets"

    brand_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("brand_profiles.id"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # logo | image | font
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    brand_profile: Mapped[BrandProfile] = relationship("BrandProfile", back_populates="assets")
