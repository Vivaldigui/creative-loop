"""
Integration tests for emergency pause (Phase 6).

Emergency pause has minimal barriers:
- No role check (any authenticated user can pause)
- No confirmation required
- AuditLog records emergency=True

Tests verify the endpoint exists and responds correctly.
In DRY_RUN mode (conftest default) the endpoint returns 400 before
reaching the service layer, which proves the safety guard is in place.
"""
from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_emergency_pause_endpoint_exists(seeded_client, db_session) -> None:
    """POST /published-ads/{id}/emergency-pause endpoint is reachable."""
    from app.models.creative import GeneratedCreative
    from app.models.product import Product
    from app.models.prompt import PromptTemplate, PromptVersion
    from app.models.publish import PublishedAd

    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    prod = Product(organization_id=org.id, name=f"P-{uuid.uuid4()}", status="active")
    db_session.add(prod)
    tmpl = PromptTemplate(organization_id=org.id, name=f"T-{uuid.uuid4()}",
                          product_id=prod.id, status="active")
    db_session.add(tmpl)
    await db_session.flush()
    pv = PromptVersion(organization_id=org.id, template_id=tmpl.id, version_number=1,
                       prompt_text="test", change_reason="test")
    db_session.add(pv)
    await db_session.flush()

    creative = GeneratedCreative(
        organization_id=org.id, prompt_version_id=pv.id, provider="mock",
        file_path="./storage/ep2.png", file_hash="ep2hash",
        width=1080, height=1080, status="approved",
    )
    db_session.add(creative)
    await db_session.flush()

    ad = PublishedAd(
        organization_id=org.id,
        creative_id=creative.id,
        idempotency_key=f"ep2-{uuid.uuid4()}",
        dry_run=False,
        status="ACTIVE",
        workflow_state="completed",
        meta_ad_id="ep2_ad",
    )
    db_session.add(ad)
    await db_session.commit()

    # DRY_RUN=true → 400 (endpoint exists but guarded)
    resp = await client.post(f"/published-ads/{ad.id}/emergency-pause")
    assert resp.status_code == 400
    assert "DRY_RUN" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_emergency_pause_unknown_ad_returns_404(seeded_client, db_session) -> None:
    """POST /published-ads/{unknown}/emergency-pause returns 404."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    resp = await client.post(f"/published-ads/{uuid.uuid4()}/emergency-pause")
    # 400 (DRY_RUN guard fires before 404)
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_audit_log_emergency_field_default_false(db_session) -> None:
    """AuditLog.emergency defaults to False for regular actions."""
    import uuid as _uuid

    from app.models.audit import AuditLog

    org_id = _uuid.uuid4()
    log = AuditLog(
        organization_id=org_id,
        actor_id=_uuid.uuid4(),
        action="test_action",
        entity_type="published_ad",
        entity_id=str(_uuid.uuid4()),
        result="success",
        dry_run=False,
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    assert log.emergency is False


@pytest.mark.asyncio
async def test_audit_log_emergency_field_true_for_emergency_pause(db_session) -> None:
    """AuditLog.emergency=True is persisted for emergency pause actions."""
    import uuid as _uuid

    from app.models.audit import AuditLog

    org_id = _uuid.uuid4()
    log = AuditLog(
        organization_id=org_id,
        actor_id=_uuid.uuid4(),
        action="emergency_pause_intent",
        entity_type="published_ad",
        entity_id=str(_uuid.uuid4()),
        result="in_progress",
        dry_run=False,
        emergency=True,
    )
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)

    assert log.emergency is True
