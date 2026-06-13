"""
Integration tests for manual activation and pause flows (Phase 6).

All tests operate against the DB directly (no real Meta calls).
Activation/pause endpoints are blocked in DRY_RUN mode, so these tests
verify the guard at the endpoint level.
"""
from __future__ import annotations

import uuid

import pytest


async def _make_creative(db_session, org_id):
    from app.models.creative import GeneratedCreative
    from app.models.product import Product
    from app.models.prompt import PromptTemplate, PromptVersion

    prod = Product(organization_id=org_id, name=f"P-{uuid.uuid4()}", status="active")
    db_session.add(prod)
    tmpl = PromptTemplate(organization_id=org_id, name=f"T-{uuid.uuid4()}",
                          product_id=prod.id, status="active")
    db_session.add(tmpl)
    await db_session.flush()
    pv = PromptVersion(organization_id=org_id, template_id=tmpl.id, version_number=1,
                       prompt_text="test", change_reason="test")
    db_session.add(pv)
    await db_session.flush()
    creative = GeneratedCreative(
        organization_id=org_id, prompt_version_id=pv.id, provider="mock",
        file_path="./storage/act.png", file_hash=f"h-{uuid.uuid4()}",
        width=1080, height=1080, status="approved",
    )
    db_session.add(creative)
    await db_session.flush()
    return creative


@pytest.mark.asyncio
async def test_activate_blocked_in_dry_run_mode(seeded_client, db_session) -> None:
    """POST /published-ads/{id}/activate returns 400 in DRY_RUN mode."""
    from app.models.publish import PublishedAd

    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    creative = await _make_creative(db_session, org.id)

    ad = PublishedAd(
        organization_id=org.id,
        creative_id=creative.id,
        idempotency_key=f"act-test-{uuid.uuid4()}",
        dry_run=False,
        status="PAUSED",
        workflow_state="completed",
        meta_ad_id="ad_act_test",
    )
    db_session.add(ad)
    await db_session.commit()

    resp = await client.post(
        f"/published-ads/{ad.id}/activate",
        json={"confirmation": "ad_act_test"},
    )
    # DRY_RUN=true in conftest → 400
    assert resp.status_code == 400
    assert "DRY_RUN" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_pause_blocked_in_dry_run_mode(seeded_client, db_session) -> None:
    """POST /published-ads/{id}/pause returns 400 in DRY_RUN mode."""
    from app.models.publish import PublishedAd

    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    creative = await _make_creative(db_session, org.id)

    ad = PublishedAd(
        organization_id=org.id,
        creative_id=creative.id,
        idempotency_key=f"pause-test-{uuid.uuid4()}",
        dry_run=False,
        status="ACTIVE",
        workflow_state="completed",
        meta_ad_id="ad_pause_test",
    )
    db_session.add(ad)
    await db_session.commit()

    resp = await client.post(f"/published-ads/{ad.id}/pause")
    assert resp.status_code == 400
    assert "DRY_RUN" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_activate_endpoint_exists_and_guards_apply(seeded_client, db_session) -> None:
    """Activation endpoint is reachable; DRY_RUN guard returns 400 before business logic."""
    from app.models.publish import PublishedAd

    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    creative = await _make_creative(db_session, org.id)

    ad = PublishedAd(
        organization_id=org.id,
        creative_id=creative.id,
        idempotency_key=f"guard-act-{uuid.uuid4()}",
        dry_run=False,
        status="PAUSED",
        workflow_state="completed",
        meta_ad_id="ad_guard_act",
    )
    db_session.add(ad)
    await db_session.commit()

    resp = await client.post(
        f"/published-ads/{ad.id}/activate",
        json={"confirmation": "ad_guard_act"},
    )
    # In DRY_RUN mode → 400 (endpoint exists but guarded)
    assert resp.status_code in (400, 403)


@pytest.mark.asyncio
async def test_published_ad_not_found_returns_404(seeded_client, db_session) -> None:
    """GET /published-ads/{unknown_id} returns 404."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    resp = await client.get(f"/published-ads/{uuid.uuid4()}")
    assert resp.status_code == 404
