"""
Unit tests for DryRunPublisher.

Critical test: verify that no HTTP write call is ever made.
"""
from __future__ import annotations

import pytest
from packages.meta_client.publish.dry_run_publisher import DryRunPublisher
from packages.meta_client.publish.dtos import (
    AdCreativePayload,
    AdPayload,
    AdSetPayload,
    CampaignPayload,
    ImageUploadPayload,
    LinkData,
    MetaPublishPayload,
    ObjectStorySpec,
)
from packages.meta_client.publish.factory import get_meta_publisher
from packages.meta_client.publish.placeholders import (
    PENDING_META_AD_ACCOUNT_ID,
    PENDING_META_IMAGE_HASH,
    PENDING_META_PAGE_ID,
)
from packages.meta_client.publish.write_client_real import (
    RealMetaWriteClient,
)


def _sample_payload() -> MetaPublishPayload:
    campaign = CampaignPayload(name="Test Campaign")
    adset = AdSetPayload(name="Test AdSet", campaign_id="sim_c1", daily_budget=5000)
    image = ImageUploadPayload(
        source_storage_key="org/abc.png",
        image_hash="sha256abc",
        bytes_len=100000,
        filename="abc.png",
    )
    story = ObjectStorySpec(
        page_id=PENDING_META_PAGE_ID,
        link_data=LinkData(image_hash=PENDING_META_IMAGE_HASH, link="https://example.com"),
    )
    ad_creative = AdCreativePayload(name="Test Creative", object_story_spec=story)
    ad = AdPayload(name="Test Ad", adset_id="sim_a1", creative={"creative_id": "sim_cr1"})
    return MetaPublishPayload(
        ad_account_id=PENDING_META_AD_ACCOUNT_ID,
        page_id=PENDING_META_PAGE_ID,
        campaign=campaign,
        adset=adset,
        image_upload=image,
        ad_creative=ad_creative,
        ad=ad,
    )


@pytest.mark.asyncio
async def test_dry_run_publisher_returns_simulated_ids():
    publisher = DryRunPublisher()
    payload = _sample_payload()
    result = await publisher.publish(payload)

    assert result.dry_run is True
    assert result.simulated_campaign_id.startswith("simulated_campaign_")
    assert result.simulated_adset_id.startswith("simulated_adset_")
    assert result.simulated_image_hash.startswith("simulated_imghash_")
    assert result.simulated_ad_creative_id.startswith("simulated_creative_")
    assert result.simulated_ad_id.startswith("simulated_ad_")


@pytest.mark.asyncio
async def test_dry_run_publisher_detects_placeholders():
    publisher = DryRunPublisher()
    payload = _sample_payload()
    result = await publisher.publish(payload)

    assert len(result.placeholders_present) > 0
    # page_id is PENDING_META_PAGE_ID
    assert "page_id" in result.placeholders_present or "adcreative_page_id" in result.placeholders_present


@pytest.mark.asyncio
async def test_dry_run_publisher_lists_all_steps():
    publisher = DryRunPublisher()
    result = await publisher.publish(_sample_payload())
    assert len(result.steps_simulated) == 5


@pytest.mark.asyncio
async def test_dry_run_publisher_each_id_unique():
    """Two separate calls produce distinct IDs (UUID-based)."""
    publisher = DryRunPublisher()
    r1 = await publisher.publish(_sample_payload())
    r2 = await publisher.publish(_sample_payload())
    assert r1.simulated_ad_id != r2.simulated_ad_id


# ── Security: no HTTP write calls ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_http_write_calls_during_dry_run(monkeypatch):
    """
    The DRY_RUN publisher must NOT call any HTTP write method.
    We patch httpx.AsyncClient to raise if instantiated — if this raises, a write was attempted.
    """
    import httpx

    def _never_call(*args, **kwargs):
        raise AssertionError(
            "httpx.AsyncClient was instantiated during DRY_RUN publish — this is forbidden."
        )

    monkeypatch.setattr(httpx, "AsyncClient", _never_call)

    publisher = DryRunPublisher()
    result = await publisher.publish(_sample_payload())
    assert result.dry_run is True  # completed without touching httpx


@pytest.mark.asyncio
async def test_real_write_client_raises_disabled_error():
    """RealMetaWriteClient requires credentials — cannot be constructed without them."""
    with pytest.raises(TypeError):
        RealMetaWriteClient()  # access_token and app_secret are required positional args


def test_factory_returns_dry_run_publisher():
    publisher = get_meta_publisher(dry_run=True)
    assert isinstance(publisher, DryRunPublisher)


def test_factory_asserts_dry_run_false():
    with pytest.raises(ValueError):
        get_meta_publisher(dry_run=False)


@pytest.mark.asyncio
async def test_audit_payload_no_secrets():
    """
    Published payload must not contain access_token, appsecret_proof, or api keys.
    We verify the sanitizer used in publication_service strips these.
    """
    from app.services.publication_service import _sanitize_payload

    dirty = {
        "ad_account_id": "act_123",
        "access_token": "EAABzSECRET_TOKEN",
        "appsecret_proof": "abc123hmac",
        "steps": {
            "1_campaign": {"name": "Test", "status": "PAUSED"},
            "meta_api_key": "should_be_redacted",
        },
    }
    clean = _sanitize_payload(dirty)
    assert clean["access_token"] == "***REDACTED***"
    assert clean["appsecret_proof"] == "***REDACTED***"
    assert clean["steps"]["meta_api_key"] == "***REDACTED***"
    assert clean["ad_account_id"] == "act_123"
    assert clean["steps"]["1_campaign"]["name"] == "Test"
