from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make packages importable
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))  # from anthropic_client import ... (direct)
sys.path.insert(0, str(ROOT))               # from packages.anthropic_client import ... (namespaced)

# Use in-memory SQLite for all tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DATABASE_DRIVER", "sqlite")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_tests_only_32bytes!")
os.environ.setdefault("ENCRYPTION_KEY", "RKDlYJiLSiZ5mxJ4qI5V6J7E2A5j2sTLDEBHbexjf8U=")
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("REQUIRE_HUMAN_APPROVAL", "true")

from app.db import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def seeded_client(db_engine, db_session):
    """Client with a pre-created org, user, and second org user for isolation tests."""
    from app.models.user import Organization, User
    from app.security.hashing import hash_password

    org = Organization(name="Org A", slug="org-a", status="active")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email="owner@orga.example",
        hashed_password=hash_password("password123"),
        full_name="Owner A",
        role="owner",
        is_active=True,
    )
    db_session.add(user)

    # Second org for isolation test
    org_b = Organization(name="Org B", slug="org-b", status="active")
    db_session.add(org_b)
    await db_session.flush()

    user_b = User(
        organization_id=org_b.id,
        email="owner@orgb.example",
        hashed_password=hash_password("password456"),
        full_name="Owner B",
        role="owner",
        is_active=True,
    )
    db_session.add(user_b)
    await db_session.commit()

    app = create_app()
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, user, org, user_b, org_b
