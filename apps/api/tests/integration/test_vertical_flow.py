"""
E2E vertical flow test (all mocked, no external API calls):
product → source-ad → analyze → generate-prompt → generate-creative → quality-check →
policy-check → approve → dry-run publish → AuditLog traceability.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_full_vertical_flow(seeded_client, db_session):
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    # 1. Create product
    r = await client.post("/products", json={"name": "TestFlow Product", "category": "Test"})
    assert r.status_code == 201
    product_id = r.json()["id"]

    # 2. Create a source-ad manually (simulate historical ad)
    from app.models.source_ad import PerformanceSnapshot, SourceAd
    ad = SourceAd(
        organization_id=org.id,
        product_id=uuid.UUID(product_id),
        name="Flow Test Ad",
        headline="Test Headline",
        body_text="Test body",
        cta="Shop Now",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.flush()  # populate ad.id before referencing as FK
    snap = PerformanceSnapshot(
        organization_id=org.id,
        source_ad_id=ad.id,
        spend=100.0,
        impressions=5000,
        clicks=150,
        roas=2.5,
        ctr=3.0,
        is_fictitious=True,
    )
    db_session.add(snap)
    await db_session.commit()

    # 3. Analyze the ad (mock)
    r = await client.post(f"/source-ads/{ad.id}/analyze")
    assert r.status_code == 200
    analysis = r.json()
    assert "visual_summary" in analysis
    assert "MOCK" in analysis["visual_summary"]
    analysis_id = analysis["id"]

    # 4. Generate prompt version
    r = await client.post("/prompts/generate", json={
        "source_ad_id": str(ad.id),
        "analysis_id": analysis_id,
        "product_id": product_id,
        "ad_format": "single_image",
        "objective": "Drive conversions",
        "fields": {"product_name": "TestFlow Product", "cta_text": "Shop Now"},
    })
    assert r.status_code == 201
    pv = r.json()
    assert pv["version_number"] == 1
    assert "Shop Now" in pv["prompt_text"]
    template_id = pv["template_id"]  # revise now uses template_id (Phase 3)

    # 5. Revise prompt — new version, diff present (id = template_id)
    r = await client.post(f"/prompts/{template_id}/revise", json={
        "fields": {"cta_text": "Buy Now"},
        "change_reason": "A/B test CTA text",
    })
    assert r.status_code == 201
    pv2 = r.json()
    assert pv2["version_number"] == 2
    assert pv2["diff_summary"] is not None
    assert "Buy Now" in pv2["prompt_text"]
    # Original version text is not overwritten (verified separately)

    # 6. Generate creative (mock provider)
    r = await client.post("/creatives", json={
        "prompt_version_id": pv2["id"],
        "width": 1080,
        "height": 1080,
    })
    assert r.status_code == 201
    creative = r.json()
    assert creative["provider"] == "mock"
    assert creative["file_hash"] is not None
    assert Path(creative["file_path"]).exists()
    creative_id = creative["id"]

    # 7a. Quality check (Phase 4: separate endpoint)
    r = await client.post(f"/creatives/{creative_id}/quality-check")
    assert r.status_code == 200
    qc = r.json()
    assert qc["result"] in ("PASS", "WARNING", "BLOCKED")

    # 7b. Policy check (Phase 4: separate endpoint)
    r = await client.post(f"/creatives/{creative_id}/policy-check")
    assert r.status_code == 200
    pc = r.json()
    assert pc["result"] in ("PASS", "WARNING", "BLOCKED")
    assert "internal_notice" in pc  # Phase 4 rule: must never claim Meta approval

    # 8. Approve the creative
    r = await client.post(f"/creatives/{creative_id}/approve", json={"comment": "Looks good"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # 9. Simulate DRY_RUN publish
    import os

    from app.config import get_settings

    os.environ["MAX_DAILY_SPEND"] = "500.0"
    get_settings.cache_clear()

    key = f"flow-{uuid.uuid4()}"
    try:
        r = await client.post("/publish/meta/dry-run", json={
            "creative_id": creative_id,
            "idempotency_key": key,
            "campaign_name": "Test Campaign",
            "headline": "Buy our product",
            "cta_type": "SHOP_NOW",
            "daily_budget_brl": 50.0,
        })
    finally:
        os.environ.pop("MAX_DAILY_SPEND", None)
        get_settings.cache_clear()

    assert r.status_code == 201
    pub = r.json()
    assert pub["dry_run"] is True
    assert pub["payload"]["steps"]["1_campaign"]["status"] == "PAUSED"

    # 10. Verify AuditLog has all actions
    from sqlalchemy import select

    from app.models.audit import AuditLog
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.organization_id == org.id).order_by(AuditLog.created_at)
    )
    logs = result.scalars().all()
    actions = [log.action for log in logs]
    assert "analyze_ad" in actions
    assert "generate_prompt" in actions
    assert "revise_prompt" in actions
    assert "generate_creative" in actions
    assert "approve_creative" in actions
    assert "publish_dry_run_result" in actions
