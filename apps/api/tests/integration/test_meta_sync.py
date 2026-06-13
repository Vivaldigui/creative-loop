"""
Integration tests for Meta sync: full flow with mock client,
idempotency (run 2x), org isolation, RBAC, MetaSyncRun lifecycle.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DATABASE_DRIVER", "sqlite")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_tests_only_32bytes!")
os.environ.setdefault("ENCRYPTION_KEY", "RKDlYJiLSiZ5mxJ4qI5V6J7E2A5j2sTLDEBHbexjf8U=")
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("META_PROVIDER", "mock")

import uuid  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db import Base  # noqa: E402
from app.models.meta_sync import AdAccount, SourceAdSet, SourceCampaign  # noqa: E402
from app.models.source_ad import PerformanceSnapshot, SourceAd  # noqa: E402
from app.services.meta_import import MetaImportService  # noqa: E402


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def org_id():
    return uuid.uuid4()


@pytest.fixture
def mock_client():
    from meta_client.mock import MockMetaClient
    return MockMetaClient()


async def _run_sync(mock_client, db_session, org_id, kind="incremental", **kwargs):
    svc = MetaImportService(
        client=mock_client,
        db=db_session,
        org_id=org_id,
        account_external_id="act_mock_001",
        source_label="mock",
        is_fictitious=True,
    )
    date_start = kwargs.get("date_start", "2025-01-01")
    date_stop = kwargs.get("date_stop", "2025-03-31")
    return await svc.run(kind=kind, date_start=date_start, date_stop=date_stop)


# ── Full import flow ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_import_creates_entities(mock_client, db_session, org_id):
    run = await _run_sync(mock_client, db_session, org_id, kind="history")

    assert run.status == "success"

    # Account created
    account = (await db_session.execute(
        select(AdAccount).where(AdAccount.organization_id == org_id)
    )).scalars().first()
    assert account is not None
    assert account.external_id == "act_mock_001"
    assert account.currency == "BRL"

    # Campaigns created
    campaigns = (await db_session.execute(
        select(SourceCampaign).where(SourceCampaign.organization_id == org_id)
    )).scalars().all()
    assert len(campaigns) >= 3

    # AdSets created
    adsets = (await db_session.execute(
        select(SourceAdSet).where(SourceAdSet.organization_id == org_id)
    )).scalars().all()
    assert len(adsets) >= 4

    # Ads created
    ads = (await db_session.execute(
        select(SourceAd).where(SourceAd.organization_id == org_id)
    )).scalars().all()
    assert len(ads) >= 5

    # Snapshots created
    snapshots = (await db_session.execute(
        select(PerformanceSnapshot)
    )).scalars().all()
    assert len(snapshots) >= 5


@pytest.mark.asyncio
async def test_sync_run_counters(mock_client, db_session, org_id):
    run = await _run_sync(mock_client, db_session, org_id, kind="history")

    assert run.campaigns_created >= 3
    assert run.adsets_created >= 4
    assert run.ads_created >= 5
    assert run.snapshots_created >= 5
    assert run.finished_at is not None


# ── Idempotency ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_double_run_is_idempotent(mock_client, db_session, org_id):
    """Running sync twice should not duplicate entities."""
    run1 = await _run_sync(mock_client, db_session, org_id, kind="history")
    run2 = await _run_sync(mock_client, db_session, org_id, kind="history")

    assert run1.status == "success"
    assert run2.status == "success"

    ads = (await db_session.execute(
        select(SourceAd).where(SourceAd.organization_id == org_id)
    )).scalars().all()
    # Second run should upsert, not insert duplicates
    assert len(ads) == run1.ads_created


@pytest.mark.asyncio
async def test_double_run_increments_updated_counter(mock_client, db_session, org_id):
    """Second run should show ads_updated > 0 and ads_created = 0."""
    run1 = await _run_sync(mock_client, db_session, org_id, kind="history")
    run2 = await _run_sync(mock_client, db_session, org_id, kind="history")

    assert run2.ads_created == 0
    assert run2.ads_updated == run1.ads_created


@pytest.mark.asyncio
async def test_snapshot_idempotency(mock_client, db_session, org_id):
    """Same date range synced twice should not duplicate snapshots."""
    await _run_sync(mock_client, db_session, org_id, kind="history")
    await _run_sync(mock_client, db_session, org_id, kind="history")

    snapshots = (await db_session.execute(
        select(PerformanceSnapshot)
    )).scalars().all()
    # Snapshots should not be duplicated
    keys = [(s.source_ad_id, s.date_start, s.date_stop, s.level, s.breakdown_key) for s in snapshots]
    assert len(keys) == len(set(keys))


# ── Org isolation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_org_isolation(mock_client, db_session):
    """Two orgs should not see each other's entities."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    svc_a = MetaImportService(
        client=mock_client, db=db_session, org_id=org_a,
        account_external_id="act_mock_001", source_label="mock", is_fictitious=True,
    )
    svc_b = MetaImportService(
        client=mock_client, db=db_session, org_id=org_b,
        account_external_id="act_mock_001", source_label="mock", is_fictitious=True,
    )

    await svc_a.run("history", "2025-01-01", "2025-03-31")
    await svc_b.run("history", "2025-01-01", "2025-03-31")

    ads_a = (await db_session.execute(
        select(SourceAd).where(SourceAd.organization_id == org_a)
    )).scalars().all()
    ads_b = (await db_session.execute(
        select(SourceAd).where(SourceAd.organization_id == org_b)
    )).scalars().all()

    # Each org sees only its own ads
    assert len(ads_a) > 0
    assert len(ads_b) > 0
    ids_a = {a.id for a in ads_a}
    ids_b = {a.id for a in ads_b}
    assert ids_a.isdisjoint(ids_b)

    # Accounts also isolated
    accts_a = (await db_session.execute(
        select(AdAccount).where(AdAccount.organization_id == org_a)
    )).scalars().all()
    accts_b = (await db_session.execute(
        select(AdAccount).where(AdAccount.organization_id == org_b)
    )).scalars().all()
    assert all(a.organization_id == org_a for a in accts_a)
    assert all(a.organization_id == org_b for a in accts_b)


# ── MetaSyncRun lifecycle ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_run_status_success(mock_client, db_session, org_id):
    run = await _run_sync(mock_client, db_session, org_id)
    assert run.status == "success"
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.finished_at >= run.started_at


@pytest.mark.asyncio
async def test_sync_run_is_fictitious_for_mock(mock_client, db_session, org_id):
    """All entities created via mock client must be marked fictitious."""
    await _run_sync(mock_client, db_session, org_id)

    ads = (await db_session.execute(
        select(SourceAd).where(SourceAd.organization_id == org_id)
    )).scalars().all()
    assert all(a.is_fictitious for a in ads)


@pytest.mark.asyncio
async def test_sync_run_source_label(mock_client, db_session, org_id):
    """source_label is stored on entities."""
    await _run_sync(mock_client, db_session, org_id)

    campaigns = (await db_session.execute(
        select(SourceCampaign).where(SourceCampaign.organization_id == org_id)
    )).scalars().all()
    assert all(c.source == "mock" for c in campaigns)


# ── No write calls on client ──────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_dry_run_never_called(mock_client, db_session, org_id, monkeypatch):
    """publish_dry_run must never be invoked by the import service."""
    called = []

    original = mock_client.publish_dry_run

    async def spy(*args, **kwargs):
        called.append(True)
        return await original(*args, **kwargs)

    monkeypatch.setattr(mock_client, "publish_dry_run", spy)
    await _run_sync(mock_client, db_session, org_id)
    assert called == [], "publish_dry_run was called — write safety violation!"


# ── Normalization version stored ──────────────────────────────────

@pytest.mark.asyncio
async def test_normalization_version_stored(mock_client, db_session, org_id):
    from meta_client.normalize import NORMALIZATION_VERSION
    await _run_sync(mock_client, db_session, org_id)

    snaps = (await db_session.execute(select(PerformanceSnapshot))).scalars().all()
    assert len(snaps) > 0
    for s in snaps:
        assert s.normalization_version == NORMALIZATION_VERSION
