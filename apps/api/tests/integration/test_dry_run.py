"""Test DRY_RUN publish flow: payload saved, no real write, AuditLog recorded."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_dry_run_requires_approval(seeded_client, db_session):
    """Creative without approval cannot be published even in DRY_RUN."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    # Create a creative via the full flow
    from app.models.creative import GeneratedCreative
    from app.models.product import Product
    from app.models.prompt import PromptTemplate, PromptVersion

    prod = Product(organization_id=org.id, name="Test Product", status="active")
    db_session.add(prod)
    tmpl = PromptTemplate(organization_id=org.id, name="Test Template", product_id=prod.id, status="active")
    db_session.add(tmpl)
    await db_session.flush()

    pv = PromptVersion(
        organization_id=org.id,
        template_id=tmpl.id,
        version_number=1,
        prompt_text="Test prompt for dry run",
        change_reason="test",
    )
    db_session.add(pv)
    await db_session.flush()

    creative = GeneratedCreative(
        organization_id=org.id,
        prompt_version_id=pv.id,
        provider="mock",
        file_path="./storage/test.png",
        file_hash="abc123",
        width=1080,
        height=1080,
        status="pending_review",
    )
    db_session.add(creative)
    await db_session.commit()

    resp = await client.post("/publish/meta/dry-run", json={
        "creative_id": str(creative.id),
        "idempotency_key": f"test-key-{uuid.uuid4()}",
        "daily_budget_brl": 50.0,
    })
    # Should fail: REQUIRE_HUMAN_APPROVAL=true and no approval record
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    blocked = detail.get("blocked", []) if isinstance(detail, dict) else []
    assert any("approval" in b.get("code", "") for b in blocked)


@pytest.mark.asyncio
async def test_dry_run_idempotency(seeded_client, db_session):
    """Same idempotency_key cannot be reused."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    import tempfile

    from PIL import Image

    from app.models.approval import Approval
    from app.models.checks import PolicyCheck, QualityCheck
    from app.models.creative import GeneratedCreative
    from app.models.product import Product
    from app.models.prompt import PromptTemplate, PromptVersion

    prod = Product(organization_id=org.id, name="P2", status="active")
    db_session.add(prod)
    tmpl = PromptTemplate(organization_id=org.id, name="T2", product_id=prod.id, status="active")
    db_session.add(tmpl)
    await db_session.flush()

    pv = PromptVersion(organization_id=org.id, template_id=tmpl.id, version_number=1,
                       prompt_text="prompt2", change_reason="test")
    db_session.add(pv)
    await db_session.flush()

    # Create a real PNG file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (1080, 1080), color=(128, 128, 128))
        img.save(f.name)
        img_path = f.name

    creative = GeneratedCreative(organization_id=org.id, prompt_version_id=pv.id, provider="mock",
                                  file_path=img_path, file_hash="hash2", width=1080, height=1080,
                                  status="approved")
    db_session.add(creative)
    await db_session.flush()

    qc = QualityCheck(organization_id=org.id, creative_id=creative.id, result="PASS", findings={"findings": []})
    pc = PolicyCheck(organization_id=org.id, creative_id=creative.id, result="PASS", findings={"findings": []})
    db_session.add(qc)
    db_session.add(pc)
    approval = Approval(organization_id=org.id, creative_id=creative.id, decision="approved",
                        decided_by=user.id, comment="ok")
    db_session.add(approval)
    await db_session.commit()

    import os

    from app.config import get_settings

    os.environ["MAX_DAILY_SPEND"] = "500.0"
    get_settings.cache_clear()

    key = f"idem-{uuid.uuid4()}"
    body = {"creative_id": str(creative.id), "idempotency_key": key, "daily_budget_brl": 50.0}

    try:
        r1 = await client.post("/publish/meta/dry-run", json=body)
        assert r1.status_code == 201

        # Same key + same payload → safe retry → 201
        r2 = await client.post("/publish/meta/dry-run", json=body)
        assert r2.status_code == 201

        # Same key + different payload → conflict → 409
        conflict_body = {**body, "daily_budget_brl": 999.0}
        r3 = await client.post("/publish/meta/dry-run", json=conflict_body)
        assert r3.status_code == 409
    finally:
        os.environ.pop("MAX_DAILY_SPEND", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_dry_run_saves_payload_no_write(seeded_client, db_session):
    """DRY_RUN stores payload in PublishedAd.dry_run=True; no real Meta call."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    import tempfile

    from PIL import Image

    from app.models.approval import Approval
    from app.models.creative import GeneratedCreative
    from app.models.product import Product
    from app.models.prompt import PromptTemplate, PromptVersion

    prod = Product(organization_id=org.id, name="P3", status="active")
    db_session.add(prod)
    tmpl = PromptTemplate(organization_id=org.id, name="T3", product_id=prod.id, status="active")
    db_session.add(tmpl)
    await db_session.flush()

    pv = PromptVersion(organization_id=org.id, template_id=tmpl.id, version_number=1,
                       prompt_text="prompt3", change_reason="test")
    db_session.add(pv)
    await db_session.flush()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        Image.new("RGB", (1080, 1080)).save(f.name)
        img_path = f.name

    creative = GeneratedCreative(organization_id=org.id, prompt_version_id=pv.id, provider="mock",
                                  file_path=img_path, file_hash="hash3", width=1080, height=1080,
                                  status="approved")
    db_session.add(creative)
    await db_session.flush()

    approval = Approval(organization_id=org.id, creative_id=creative.id, decision="approved",
                        decided_by=user.id, comment="ok")
    db_session.add(approval)
    await db_session.commit()

    import os

    from app.config import get_settings

    os.environ["MAX_DAILY_SPEND"] = "500.0"
    get_settings.cache_clear()

    key = f"idem3-{uuid.uuid4()}"
    try:
        resp = await client.post("/publish/meta/dry-run", json={
            "creative_id": str(creative.id),
            "idempotency_key": key,
            "daily_budget_brl": 50.0,
        })
    finally:
        os.environ.pop("MAX_DAILY_SPEND", None)
        get_settings.cache_clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["dry_run"] is True
    assert "payload" in body
    assert "No real Meta API call" in body["message"]

    # Verify AuditLog — result record written after simulation
    from app.models.audit import AuditLog
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "publish_dry_run_result")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.dry_run is True
