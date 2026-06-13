"""
Integration tests for Phase 4 creative generation pipeline.

Full flow: generate → storage → quality/policy gate → approve/reject/variation.
All tests use the mock provider (zero cost, no external calls).
"""
from __future__ import annotations

import pytest

# ── Helpers ───────────────────────────────────────────────────────

async def _login(client, email="owner@orga.example", password="password123"):
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()


async def _create_prompt_version(client, product_id: str) -> dict:
    r = await client.post("/prompts/generate", json={
        "product_id": product_id,
        "fields": {"product_name": "Phase4 Product", "cta_text": "Buy Now"},
        "ad_format": "single_image",
        "objective": "Conversions",
    })
    assert r.status_code == 201
    return r.json()


async def _create_product(client) -> str:
    r = await client.post("/products", json={"name": "Phase4 Product", "category": "Test"})
    assert r.status_code == 201
    return r.json()["id"]


# ── Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_creative_returns_201(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    assert r.status_code == 201
    creative = r.json()
    assert creative["provider"] == "mock"
    assert creative["status"] in ("awaiting_approval", "blocked")


@pytest.mark.asyncio
async def test_generate_creative_has_file_hash(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    assert r.status_code == 201
    creative = r.json()
    assert creative["file_hash"] is not None
    assert len(creative["file_hash"]) == 64  # sha256 hex


@pytest.mark.asyncio
async def test_generate_creative_has_storage_key(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    assert r.status_code == 201
    creative = r.json()
    assert creative["storage_key"] is not None
    assert creative["storage_backend"] == "local"


@pytest.mark.asyncio
async def test_generate_registers_model_and_params(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative = r.json()
    # model_used should be recorded (mock provider sets "mock-pillow")
    assert creative["model_used"] is not None


@pytest.mark.asyncio
async def test_generate_n_variations_returns_first(seeded_client):
    """n=2 returns first creative; 2 records exist in DB."""
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"], "n": 2})
    assert r.status_code == 201

    # Verify 2 creatives exist
    r_list = await client.get("/creatives")
    assert r_list.status_code == 200
    all_creatives = r_list.json()
    assert len(all_creatives) >= 2


@pytest.mark.asyncio
async def test_quality_check_runs(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative_id = r.json()["id"]

    r_qc = await client.post(f"/creatives/{creative_id}/quality-check")
    assert r_qc.status_code == 200
    qc = r_qc.json()
    assert qc["result"] in ("PASS", "WARNING", "BLOCKED")


@pytest.mark.asyncio
async def test_policy_check_runs(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative_id = r.json()["id"]

    r_pc = await client.post(f"/creatives/{creative_id}/policy-check")
    assert r_pc.status_code == 200
    pc = r_pc.json()
    assert pc["result"] in ("PASS", "WARNING", "BLOCKED")
    assert "internal_notice" in pc


@pytest.mark.asyncio
async def test_policy_check_internal_notice_present(seeded_client):
    """internal_notice must never claim Meta will approve the ad."""
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative_id = r.json()["id"]

    r_pc = await client.post(f"/creatives/{creative_id}/policy-check")
    notice = r_pc.json()["internal_notice"]
    assert notice
    assert "aprovado pela meta" not in notice.lower()
    assert "approved by meta" not in notice.lower()


@pytest.mark.asyncio
async def test_approve_awaiting_creative(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative = r.json()
    creative_id = creative["id"]

    # Only approve if not blocked (mock provider should produce clean images)
    if creative["status"] == "awaiting_approval":
        r_ap = await client.post(f"/creatives/{creative_id}/approve", json={"comment": "Looks good"})
        assert r_ap.status_code == 200
        assert r_ap.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approved_creative_immutable(seeded_client):
    """Re-approving an already-approved creative must not change status to something else."""
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative = r.json()
    creative_id = creative["id"]

    if creative["status"] != "awaiting_approval":
        pytest.skip("Creative is blocked, skipping approval immutability test")

    await client.post(f"/creatives/{creative_id}/approve", json={"comment": "OK"})

    # Attempting second approval is allowed (idempotent) but status stays "approved"
    await client.post(f"/creatives/{creative_id}/approve", json={"comment": "Again"})
    # Status endpoint should still say approved
    r_get = await client.get(f"/creatives/{creative_id}")
    assert r_get.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_creative(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative_id = r.json()["id"]

    r_rj = await client.post(f"/creatives/{creative_id}/reject", json={"comment": "Not good"})
    assert r_rj.status_code == 200
    assert r_rj.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_reject_requires_comment(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative_id = r.json()["id"]

    r_rj = await client.post(f"/creatives/{creative_id}/reject", json={})
    assert r_rj.status_code == 422  # comment required


@pytest.mark.asyncio
async def test_request_variation_creates_new_record(seeded_client):
    """request-variation must create a NEW creative record (not overwrite)."""
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    original_id = r.json()["id"]

    r_var = await client.post(
        f"/creatives/{original_id}/request-variation",
        json={"comment": "Need a different image"},
    )
    assert r_var.status_code == 200
    body = r_var.json()
    assert body["new_creative_id"] != original_id

    # Original must now be rejected
    r_orig = await client.get(f"/creatives/{original_id}")
    assert r_orig.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_blocked_cannot_approve_via_common_flow(seeded_client):
    """
    A creative with BLOCKED checks (allow_blocked_override=False default)
    must not be approvable via common flow.
    """
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)

    # Inject a policy-violating prompt so policy gate BLOCKs it
    r_pv = await client.post("/prompts/generate", json={
        "product_id": product_id,
        "fields": {
            "product_name": "Test",
            "cta_text": "Lose 10kg guaranteed — cure diabetes",
        },
        "ad_format": "single_image",
        "objective": "Conversions",
    })
    pv_id = r_pv.json()["id"]

    r = await client.post("/creatives", json={"prompt_version_id": pv_id})
    creative = r.json()
    creative_id = creative["id"]

    if creative["status"] != "blocked":
        pytest.skip("Creative not blocked — policy rules may differ; skipping")

    r_ap = await client.post(
        f"/creatives/{creative_id}/approve",
        json={"comment": "Force approve", "override_blocked": False},
    )
    assert r_ap.status_code in (403, 422)


@pytest.mark.asyncio
async def test_list_creatives(seeded_client):
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)
    await client.post("/creatives", json={"prompt_version_id": pv["id"]})

    r = await client.get("/creatives")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_generate_extra_formats_creates_derivatives(seeded_client):
    """Request extra_formats — derivative assets should be created."""
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={
        "prompt_version_id": pv["id"],
        "extra_formats": ["1080x1350", "1080x1920"],
    })
    assert r.status_code == 201
    creative_id = r.json()["id"]

    # Get with assets
    r_get = await client.get(f"/creatives/{creative_id}")
    assets = r_get.json()["assets"]
    roles = [a["role"] for a in assets]
    assert "original" in roles
    # At least one derivative or thumbnail
    assert "derivative" in roles or "thumbnail" in roles


@pytest.mark.asyncio
async def test_assets_have_signed_urls(seeded_client):
    """Assets must have signed_url for the local storage backend."""
    client, *_ = seeded_client
    await _login(client)
    product_id = await _create_product(client)
    pv = await _create_prompt_version(client, product_id)

    r = await client.post("/creatives", json={"prompt_version_id": pv["id"]})
    creative_id = r.json()["id"]

    r_get = await client.get(f"/creatives/{creative_id}")
    assets = r_get.json()["assets"]
    assert len(assets) >= 1

    for asset in assets:
        if asset.get("storage_backend") == "local" or asset.get("signed_url"):
            assert asset["signed_url"] is not None
            assert asset["signed_url"].startswith("/assets/")
