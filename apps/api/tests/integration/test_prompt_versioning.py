"""
Integration tests for Phase 3 prompt versioning.
Tests: generate v1, revise→v2, immutability, diff, identical revision rejected,
       list versions, org isolation, traceability.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_generate_creates_version_1(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r = await client.post("/prompts/generate", json={
        "ad_format": "single_image",
        "objective": "Drive sales",
        "fields": {"product_name": "Widget X", "cta_text": "Buy Now"},
    })
    assert r.status_code == 201
    pv = r.json()
    assert pv["version_number"] == 1
    assert "Widget X" in pv["prompt_text"]
    assert pv["content_hash"] is not None
    assert pv["author_type"] == "human"


@pytest.mark.asyncio
async def test_revise_creates_version_2_with_diff(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r = await client.post("/prompts/generate", json={
        "ad_format": "feed",
        "fields": {"product_name": "Old Product", "cta_text": "Shop"},
    })
    template_id = r.json()["template_id"]

    r2 = await client.post(f"/prompts/{template_id}/revise", json={
        "fields": {"cta_text": "Order Now"},
        "change_reason": "A/B test CTA",
    })
    assert r2.status_code == 201
    pv2 = r2.json()
    assert pv2["version_number"] == 2
    assert pv2["diff_summary"] is not None
    assert "-CTA: Shop" in pv2["diff_summary"] or "Shop" in pv2["diff_summary"]
    assert "Order Now" in pv2["prompt_text"]
    assert pv2["change_reason"] == "A/B test CTA"


@pytest.mark.asyncio
async def test_v1_unchanged_after_revise(seeded_client, db_session):
    """Original PromptVersion row is NEVER modified by revise."""
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r1 = await client.post("/prompts/generate", json={
        "ad_format": "feed",
        "fields": {"cta_text": "Original CTA"},
    })
    v1_id = r1.json()["id"]
    template_id = r1.json()["template_id"]
    original_text = r1.json()["prompt_text"]

    await client.post(f"/prompts/{template_id}/revise", json={
        "fields": {"cta_text": "New CTA"},
        "change_reason": "test",
    })

    # v1 must be unchanged
    import uuid

    from sqlalchemy import select

    from app.models.prompt import PromptVersion
    result = await db_session.execute(
        select(PromptVersion).where(PromptVersion.id == uuid.UUID(v1_id))
    )
    v1 = result.scalar_one()
    assert v1.prompt_text == original_text


@pytest.mark.asyncio
async def test_identical_revision_returns_409(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r = await client.post("/prompts/generate", json={
        "ad_format": "feed",
        "fields": {"cta_text": "Same CTA"},
    })
    template_id = r.json()["template_id"]

    # Revise with identical fields → 409
    r2 = await client.post(f"/prompts/{template_id}/revise", json={
        "fields": {"cta_text": "Same CTA"},
        "change_reason": "no change",
    })
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_list_versions(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r = await client.post("/prompts/generate", json={
        "ad_format": "feed",
        "fields": {"cta_text": "CTA1"},
    })
    template_id = r.json()["template_id"]
    await client.post(f"/prompts/{template_id}/revise", json={
        "fields": {"cta_text": "CTA2"},
        "change_reason": "test",
    })

    r3 = await client.get(f"/prompts/{template_id}/versions")
    assert r3.status_code == 200
    versions = r3.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2


@pytest.mark.asyncio
async def test_diff_between_versions(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r = await client.post("/prompts/generate", json={
        "ad_format": "feed",
        "fields": {"cta_text": "CTA Original"},
    })
    v1_id = r.json()["id"]
    template_id = r.json()["template_id"]

    r2 = await client.post(f"/prompts/{template_id}/revise", json={
        "fields": {"cta_text": "CTA Revised"},
        "change_reason": "revise",
    })
    v2_id = r2.json()["id"]

    r3 = await client.get(f"/prompt-versions/{v1_id}/diff/{v2_id}")
    assert r3.status_code == 200
    diff = r3.json()
    assert "unified_diff" in diff
    assert "field_changes" in diff
    assert diff["changed_field_count"] >= 1
    assert "cta_text" in diff["field_changes"]


@pytest.mark.asyncio
async def test_diff_across_templates_fails(seeded_client):
    """Diff of versions from different templates returns 422."""
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r1 = await client.post("/prompts/generate", json={
        "ad_format": "feed", "fields": {"cta_text": "CTA A"},
    })
    r2 = await client.post("/prompts/generate", json={
        "ad_format": "feed", "fields": {"cta_text": "CTA B"},
    })

    r3 = await client.get(f"/prompt-versions/{r1.json()['id']}/diff/{r2.json()['id']}")
    assert r3.status_code == 422


@pytest.mark.asyncio
async def test_get_prompt_template_detail(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    r = await client.post("/prompts/generate", json={
        "ad_format": "feed",
        "fields": {"cta_text": "X"},
        "template_name": "Test Template",
    })
    template_id = r.json()["template_id"]

    r2 = await client.get(f"/prompts/{template_id}")
    assert r2.status_code == 200
    tmpl = r2.json()
    assert tmpl["name"] == "Test Template"
    assert tmpl["version_count"] == 1
    assert tmpl["latest_version"]["version_number"] == 1


@pytest.mark.asyncio
async def test_list_prompts(seeded_client):
    client, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    await client.post("/prompts/generate", json={
        "ad_format": "feed", "fields": {"cta_text": "A"},
    })
    r = await client.get("/prompts")
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_traceability_hypothesis_to_prompt(seeded_client, db_session):
    """SourceAd → analysis → hypothesis → PromptTemplate chain is stored."""
    client, user, org, *_ = seeded_client
    await client.post("/auth/login", json={"email": "owner@orga.example", "password": "password123"})

    from app.models.source_ad import SourceAd
    ad = SourceAd(
        organization_id=org.id,
        name="Traceability Ad",
        is_fictitious=True,
        status="active",
    )
    db_session.add(ad)
    await db_session.commit()

    # Analyze
    r = await client.post(f"/source-ads/{ad.id}/analyze")
    analysis_id = r.json()["id"]

    # Generate prompt with inline hypothesis
    r2 = await client.post("/prompts/generate", json={
        "source_ad_id": str(ad.id),
        "analysis_id": analysis_id,
        "ad_format": "feed",
        "fields": {"cta_text": "Trace CTA"},
        "hypothesis_payload": {
            "statement": "A lifestyle background increases CTR",
            "primary_variable": "background",
            "expected_effect": "higher_ctr",
            "confidence": 0.6,
            "source_ad_id": str(ad.id),
            "analysis_id": analysis_id,
        },
    })
    assert r2.status_code == 201
    pv = r2.json()

    # Verify template has hypothesis_id
    template_id = pv["template_id"]
    r3 = await client.get(f"/prompts/{template_id}")
    assert r3.json()["hypothesis_id"] is not None

    # Verify analysis FK
    import uuid

    from sqlalchemy import select

    from app.models.prompt import PromptVersion
    result = await db_session.execute(
        select(PromptVersion).where(PromptVersion.id == uuid.UUID(pv["id"]))
    )
    db_pv = result.scalar_one()
    assert db_pv.analysis_id == uuid.UUID(analysis_id)
    assert db_pv.source_ad_id == ad.id
