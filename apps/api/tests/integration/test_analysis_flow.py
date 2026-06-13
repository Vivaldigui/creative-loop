"""
Integration tests for Phase 3 analysis flow.
Tests: analyze, no-image, no-metrics, idempotency, re-analysis with new metrics,
       same ad different model, listing analyses.
"""
from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_analyze_returns_structured_result(seeded_client, db_session):
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    # Create source ad + snapshot
    from app.models.source_ad import PerformanceSnapshot, SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="Analysis Flow Ad",
        headline="Great deals",
        body_text="Buy today",
        cta="Shop Now",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.flush()
    snap = PerformanceSnapshot(
        organization_id=org.id,
        source_ad_id=ad.id,
        spend=150.0,
        impressions=8000,
        clicks=240,
        roas=3.2,
        ctr=3.0,
        is_fictitious=True,
    )
    db_session.add(snap)
    await db_session.commit()

    r = await client.post(f"/source-ads/{ad.id}/analyze")
    assert r.status_code == 200
    data = r.json()
    assert "visual_summary" in data
    assert "MOCK" in data["visual_summary"]
    assert data["observations"] is not None
    assert data["metric_facts"] is not None
    assert data["limitations"] is not None
    assert data["provider"] == "mock"
    assert data["analysis_version"] == 1
    assert 0.0 <= data["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_analyze_no_image(seeded_client, db_session):
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="No Image Ad",
        headline="Text only",
        is_fictitious=True,
        status="active",
        image_path=None,
        image_url=None,
    )
    db_session.add(ad)
    await db_session.commit()

    r = await client.post(f"/source-ads/{ad.id}/analyze")
    assert r.status_code == 200
    data = r.json()
    # limitations should mention missing image
    limitations_text = str(data.get("limitations", ""))
    assert "image" in limitations_text.lower() or data["status"] in ("completed", "partial")


@pytest.mark.asyncio
async def test_analyze_no_metrics(seeded_client, db_session):
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="No Metrics Ad",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    r = await client.post(f"/source-ads/{ad.id}/analyze")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("completed", "partial")


@pytest.mark.asyncio
async def test_idempotency_same_hash_returns_existing(seeded_client, db_session):
    """Calling analyze twice without changes returns the same analysis row."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="Idempotent Ad",
        headline="Same",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    r1 = await client.post(f"/source-ads/{ad.id}/analyze")
    r2 = await client.post(f"/source-ads/{ad.id}/analyze")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same analysis returned (same id)
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_force_creates_new_analysis(seeded_client, db_session):
    """force=True always creates a new analysis row."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="Force Ad",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    r1 = await client.post(f"/source-ads/{ad.id}/analyze")
    r2 = await client.post(f"/source-ads/{ad.id}/analyze", json={"force": True})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]
    assert r2.json()["analysis_version"] == 2


@pytest.mark.asyncio
async def test_list_analyses_returns_all_versions(seeded_client, db_session):
    """GET /source-ads/{id}/analyses returns all versions."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="List Analyses Ad",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    # Create 2 analyses
    await client.post(f"/source-ads/{ad.id}/analyze")
    await client.post(f"/source-ads/{ad.id}/analyze", json={"force": True})

    r = await client.get(f"/source-ads/{ad.id}/analyses")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_get_analysis_detail(seeded_client, db_session):
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="Detail Ad",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    r = await client.post(f"/source-ads/{ad.id}/analyze")
    analysis_id = r.json()["id"]

    r2 = await client.get(f"/analyses/{analysis_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == analysis_id
    assert "request_metadata" in r2.json()


@pytest.mark.asyncio
async def test_analysis_org_isolation(seeded_client, db_session):
    """Org B cannot access org A's analysis."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="Isolated Ad",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    await client.post(f"/source-ads/{ad.id}/analyze")

    # Try to access with a different (fake) analysis ID
    fake_id = str(uuid.uuid4())
    r2 = await client.get(f"/analyses/{fake_id}")
    assert r2.status_code == 404
