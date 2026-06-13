"""
Integration tests for approval queue endpoints.

GET /approvals            — approval queue
GET /approvals/{id}       — approval detail with signed URLs
"""
from __future__ import annotations

import pytest


async def _login(client, email="owner@orga.example", password="password123"):
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200


async def _setup_creative(client) -> str:
    r_prod = await client.post("/products", json={"name": "ApprovalTest", "category": "T"})
    product_id = r_prod.json()["id"]

    r_pv = await client.post("/prompts/generate", json={
        "product_id": product_id,
        "fields": {"product_name": "ApprovalTest", "cta_text": "Learn More"},
        "ad_format": "single_image",
        "objective": "Awareness",
    })
    pv_id = r_pv.json()["id"]

    r_c = await client.post("/creatives", json={"prompt_version_id": pv_id})
    assert r_c.status_code == 201
    return r_c.json()["id"]


# ── GET /approvals ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approvals_list_returns_200(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    await _setup_creative(client)

    r = await client.get("/approvals")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_approvals_list_contains_generated_creative(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r = await client.get("/approvals?include_blocked=true")
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()]
    assert creative_id in ids


@pytest.mark.asyncio
async def test_approvals_list_item_has_status(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    await _setup_creative(client)

    r = await client.get("/approvals")
    items = r.json()
    if items:
        assert items[0]["status"] in ("awaiting_approval", "blocked")


@pytest.mark.asyncio
async def test_approvals_list_item_has_provider(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    await _setup_creative(client)

    r = await client.get("/approvals")
    items = r.json()
    if items:
        assert items[0]["provider"] == "mock"


@pytest.mark.asyncio
async def test_approvals_not_accessible_after_approve(seeded_client):
    """Approved creatives must no longer appear in approval queue."""
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    # Only approve if not blocked
    r_c = await client.get(f"/creatives/{creative_id}")
    if r_c.json()["status"] == "awaiting_approval":
        await client.post(f"/creatives/{creative_id}/approve", json={"comment": "OK"})

    r = await client.get("/approvals")
    ids = [item["id"] for item in r.json()]
    assert creative_id not in ids


# ── GET /approvals/{id} ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_approval_detail_returns_200(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r = await client.get(f"/approvals/{creative_id}")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_approval_detail_has_prompt_text(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r = await client.get(f"/approvals/{creative_id}")
    data = r.json()
    assert data["prompt_text"] is not None


@pytest.mark.asyncio
async def test_approval_detail_has_internal_notice(seeded_client):
    """Detail MUST include internal_notice that never claims Meta approval."""
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r = await client.get(f"/approvals/{creative_id}")
    notice = r.json()["internal_notice"]
    assert notice
    assert "aprovado pela meta" not in notice.lower()
    assert "approved by meta" not in notice.lower()


@pytest.mark.asyncio
async def test_approval_detail_has_assets(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r = await client.get(f"/approvals/{creative_id}")
    data = r.json()
    assert "assets" in data
    assert isinstance(data["assets"], list)


@pytest.mark.asyncio
async def test_approval_detail_assets_have_signed_url(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r = await client.get(f"/approvals/{creative_id}")
    assets = r.json()["assets"]
    assert len(assets) >= 1
    for asset in assets:
        if asset.get("signed_url"):
            assert asset["signed_url"].startswith("/assets/")


@pytest.mark.asyncio
async def test_approval_detail_not_found_404(seeded_client):
    client, *_ = seeded_client
    await _login(client)

    import uuid
    r = await client.get(f"/approvals/{uuid.uuid4()}")
    assert r.status_code == 404


# ── Org isolation ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approvals_isolated_between_orgs(seeded_client):
    """Org B must not see Org A's creatives in the approval queue."""
    client, user_a, org_a, user_b, org_b = seeded_client

    # Org A creates a creative
    await _login(client, "owner@orga.example", "password123")
    creative_id = await _setup_creative(client)

    # Org B logs in
    await client.post("/auth/logout", json={})
    await _login(client, "owner@orgb.example", "password456")

    r = await client.get("/approvals?include_blocked=true")
    ids = [item["id"] for item in r.json()]
    assert creative_id not in ids


# ── Audit trail ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_creates_audit_log(seeded_client, db_session):
    client, user, org, *_ = seeded_client
    await _login(client)
    creative_id = await _setup_creative(client)

    r_c = await client.get(f"/creatives/{creative_id}")
    if r_c.json()["status"] != "awaiting_approval":
        pytest.skip("Creative is blocked, cannot test approval audit")

    await client.post(f"/creatives/{creative_id}/approve", json={"comment": "Audited"})

    from sqlalchemy import select

    from app.models.audit import AuditLog

    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.organization_id == org.id,
            AuditLog.action == "approve_creative",
        )
    )
    logs = result.scalars().all()
    assert len(logs) >= 1
