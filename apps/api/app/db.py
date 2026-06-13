from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator

from app.config import get_settings

# ── Portable UUID type (Postgres native / SQLite string) ─────────

class UUIDType(TypeDecorator):
    """Store UUID as native PG UUID or as VARCHAR(36) for SQLite."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value if dialect.name == "postgresql" else str(value)
        return uuid.UUID(str(value)) if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(str(value))


# ── Portable JSONB (Postgres JSONB / SQLite JSON) ─────────────────

class JSONBType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


# ── Declarative base ─────────────────────────────────────────────

class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSONBType,
    }


# ── Common mixins ────────────────────────────────────────────────

class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class OrgMixin:
    organization_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)


class StatusMixin:
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")


class VersionMixin:
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class SourceMixin:
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MetadataMixin:
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONBType, nullable=True
    )


# ── Engine & session factory ─────────────────────────────────────

_engine = None
_SessionLocal = None


def _make_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        future=True,
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _SessionLocal


async def get_db() -> AsyncSession:  # type: ignore[return]
    factory = get_session_factory()
    async with factory() as session:
        yield session
