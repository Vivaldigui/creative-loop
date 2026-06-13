"""
Unit tests for idempotency tag and reconciliation in RealPublisher.

Reconciliation:
  Before each non-idempotent create, search Meta for existing resource by tag.
  If found, reuse it rather than creating a duplicate.

Uses respx for HTTP mocking — no real Meta calls.
"""
from __future__ import annotations

import httpx
import pytest
import respx
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
from packages.meta_client.publish.placeholders import PENDING_META_IMAGE_HASH, PENDING_META_PAGE_ID
from packages.meta_client.publish.real_publisher import PartialProgress, RealPublisher
from packages.meta_client.publish.write_client_real import RealMetaWriteClient

BASE = "https://graph.facebook.com/v21.0"
TAG = "testtagabc1"
ACCOUNT = "act_1234"


@pytest.fixture
def write_client() -> RealMetaWriteClient:
    return RealMetaWriteClient(
        access_token="tok",
        app_secret="sec",
        api_version="v21.0",
        max_retries=1,
        timeout_s=5.0,
    )


def _sample_payload() -> MetaPublishPayload:
    campaign = CampaignPayload(name=f"Test Campaign [{TAG}]")
    adset = AdSetPayload(name=f"Test AdSet [{TAG}]", campaign_id="c1", daily_budget=5000)
    image = ImageUploadPayload(
        source_storage_key="org/img.png",
        image_hash="sha256abc",
        bytes_len=100000,
        filename="test.png",
    )
    story = ObjectStorySpec(
        page_id=PENDING_META_PAGE_ID,
        link_data=LinkData(image_hash=PENDING_META_IMAGE_HASH, link="https://example.com"),
    )
    ad_creative = AdCreativePayload(name=f"Test Creative [{TAG}]", object_story_spec=story)
    ad = AdPayload(name=f"Test Ad [{TAG}]", adset_id="a1", creative={"creative_id": "cr1"})
    return MetaPublishPayload(
        ad_account_id=ACCOUNT,
        page_id=PENDING_META_PAGE_ID,
        campaign=campaign,
        adset=adset,
        image_upload=image,
        ad_creative=ad_creative,
        ad=ad,
    )


@respx.mock
@pytest.mark.asyncio
async def test_resume_skips_image_upload_when_already_uploaded(write_client: RealMetaWriteClient) -> None:
    """If image was already uploaded, publisher must not call upload again."""
    # Set up mocks for remaining steps (no adimages mock — it must not be called)
    respx.get(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "camp_1"})
    )
    respx.get(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"id": "adset_1"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adcreatives").mock(
        return_value=httpx.Response(200, json={"id": "creative_1"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/ads").mock(
        return_value=httpx.Response(200, json={"id": "ad_1"})
    )
    respx.get(f"{BASE}/ad_1").mock(
        return_value=httpx.Response(
            200, json={"effective_status": "PAUSED", "id": "ad_1"}
        )
    )

    publisher = RealPublisher(client=write_client, idempotency_tag=TAG)
    progress = PartialProgress(image_hash="already_uploaded_hash")
    payload = _sample_payload()
    object.__setattr__(payload.image_upload, "_raw_bytes", b"fake_bytes")

    result = await publisher.publish(payload, resume_from=progress)

    assert result.meta_image_hash == "already_uploaded_hash"
    # Image upload endpoint should not have been called
    upload_calls = [r for r in respx.calls if "adimages" in str(r.request.url)]
    assert not upload_calls, "Should not upload image when resuming with existing hash"


@respx.mock
@pytest.mark.asyncio
async def test_full_publish_happy_path_returns_completed(write_client: RealMetaWriteClient) -> None:
    """All 6 steps succeed → workflow_state == 'completed'."""
    respx.post(f"{BASE}/{ACCOUNT}/adimages").mock(
        return_value=httpx.Response(
            200, json={"images": {"test.png": {"hash": "img_hash_real"}}}
        )
    )
    respx.get(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "camp_new"})
    )
    respx.get(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"id": "adset_new"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adcreatives").mock(
        return_value=httpx.Response(200, json={"id": "creative_new"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/ads").mock(
        return_value=httpx.Response(200, json={"id": "ad_new"})
    )
    respx.get(f"{BASE}/ad_new").mock(
        return_value=httpx.Response(
            200, json={"effective_status": "PAUSED", "id": "ad_new"}
        )
    )

    publisher = RealPublisher(client=write_client, idempotency_tag=TAG)
    payload = _sample_payload()
    object.__setattr__(payload.image_upload, "_raw_bytes", b"fake_image_bytes")

    result = await publisher.publish(payload, correlation_id="test-corr-id")

    assert result.succeeded, f"Expected succeeded, got: {result.workflow_state}: {result.error_detail}"
    assert result.meta_ad_id == "ad_new"
    assert result.meta_campaign_id == "camp_new"
    assert result.meta_image_hash == "img_hash_real"


@respx.mock
@pytest.mark.asyncio
async def test_active_status_after_create_triggers_manual_review(write_client: RealMetaWriteClient) -> None:
    """If Meta returns ACTIVE after ad creation, publisher transitions to requires_manual_review."""
    respx.post(f"{BASE}/{ACCOUNT}/adimages").mock(
        return_value=httpx.Response(200, json={"images": {"test.png": {"hash": "h1"}}})
    )
    respx.get(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "c1"})
    )
    respx.get(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adcreatives").mock(
        return_value=httpx.Response(200, json={"id": "cr1"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/ads").mock(
        return_value=httpx.Response(200, json={"id": "ad1"})
    )
    # Meta unexpectedly returns ACTIVE
    respx.get(f"{BASE}/ad1").mock(
        return_value=httpx.Response(200, json={"effective_status": "ACTIVE", "id": "ad1"})
    )

    publisher = RealPublisher(client=write_client, idempotency_tag=TAG)
    payload = _sample_payload()
    object.__setattr__(payload.image_upload, "_raw_bytes", b"fake")

    result = await publisher.publish(payload)

    assert result.workflow_state == "requires_manual_review"
    assert result.requires_manual_review is True
    assert not result.succeeded


@respx.mock
@pytest.mark.asyncio
async def test_existing_campaign_is_reused_not_recreated(write_client: RealMetaWriteClient) -> None:
    """If campaign with idempotency tag already exists, publisher reuses it and skips POST."""
    respx.post(f"{BASE}/{ACCOUNT}/adimages").mock(
        return_value=httpx.Response(200, json={"images": {"test.png": {"hash": "img_h"}}})
    )
    # Campaign search returns existing campaign with tag — publisher should reuse it
    respx.get(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "existing_camp", "name": f"My Campaign [{TAG}]", "status": "PAUSED"}]},
        )
    )
    # Campaign POST is not expected, but register it so respx doesn't complain if called
    campaign_post = respx.post(f"{BASE}/{ACCOUNT}/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "new_camp_SHOULD_NOT_BE_CREATED"})
    )

    respx.get(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adsets").mock(
        return_value=httpx.Response(200, json={"id": "adset_new"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/adcreatives").mock(
        return_value=httpx.Response(200, json={"id": "cr_new"})
    )
    respx.post(f"{BASE}/{ACCOUNT}/ads").mock(
        return_value=httpx.Response(200, json={"id": "ad_new"})
    )
    respx.get(f"{BASE}/ad_new").mock(
        return_value=httpx.Response(200, json={"effective_status": "PAUSED", "id": "ad_new"})
    )

    publisher = RealPublisher(client=write_client, idempotency_tag=TAG)
    payload = _sample_payload()
    object.__setattr__(payload.image_upload, "_raw_bytes", b"fake")

    result = await publisher.publish(payload)

    # Verify publisher reused existing campaign, not created a new one
    assert campaign_post.call_count == 0, "Should not POST a new campaign when one already exists"
    assert result.meta_campaign_id == "existing_camp"
