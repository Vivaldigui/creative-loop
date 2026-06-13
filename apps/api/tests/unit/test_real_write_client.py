"""
Unit tests for RealMetaWriteClient.

Uses respx to mock httpx calls — zero real HTTP.
Tests: PAUSED enforcement, status queries, find_by_idempotency_tag, image upload.
"""
from __future__ import annotations

import httpx
import pytest
import respx
from packages.meta_client.publish.write_client_real import RealMetaWriteClient

BASE = "https://graph.facebook.com/v21.0"


@pytest.fixture
def client() -> RealMetaWriteClient:
    return RealMetaWriteClient(
        access_token="tok_test",
        app_secret="secret_test",
        api_version="v21.0",
        max_retries=1,
        timeout_s=5.0,
    )


@respx.mock
@pytest.mark.asyncio
async def test_create_campaign_returns_id(client: RealMetaWriteClient) -> None:
    respx.post(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(200, json={"id": "camp_abc"}, headers={"x-fb-request-id": "r1"})
    )
    body, req_id = await client.create_campaign(
        "act_1234",
        {"name": "Test Campaign [abc]", "objective": "OUTCOME_TRAFFIC", "status": "PAUSED",
         "special_ad_categories": []},
    )
    assert body["id"] == "camp_abc"
    assert req_id == "r1"


@pytest.mark.asyncio
async def test_create_campaign_rejects_non_paused_payload(client: RealMetaWriteClient) -> None:
    """create_campaign must raise if status != PAUSED before any HTTP call."""
    with pytest.raises((AssertionError, ValueError)):
        await client.create_campaign("act_1234", {"name": "x", "status": "ACTIVE"})


@pytest.mark.asyncio
async def test_create_adset_rejects_non_paused_payload(client: RealMetaWriteClient) -> None:
    with pytest.raises((AssertionError, ValueError)):
        await client.create_adset("act_1234", {"name": "x", "status": "ACTIVE"})


@pytest.mark.asyncio
async def test_create_ad_rejects_non_paused_payload(client: RealMetaWriteClient) -> None:
    """create_ad must raise if status != PAUSED — the DTO validator forces it but we test the client guard."""
    with pytest.raises((AssertionError, ValueError)):
        await client.create_ad("act_1234", {"name": "x", "adset_id": "a", "status": "ACTIVE"})


@respx.mock
@pytest.mark.asyncio
async def test_get_status_returns_effective_status(client: RealMetaWriteClient) -> None:
    respx.get(f"{BASE}/ad_1").mock(
        return_value=httpx.Response(
            200, json={"id": "ad_1", "effective_status": "PAUSED", "configured_status": "PAUSED"}
        )
    )
    body, _ = await client.get_status("ad_1")
    assert body["effective_status"] == "PAUSED"


@respx.mock
@pytest.mark.asyncio
async def test_update_ad_status_paused(client: RealMetaWriteClient) -> None:
    respx.post(f"{BASE}/ad_1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    body, _ = await client.update_ad_status("ad_1", "PAUSED")
    assert body["success"] is True


@respx.mock
@pytest.mark.asyncio
async def test_find_by_idempotency_tag_returns_first_matching(client: RealMetaWriteClient) -> None:
    """find_by_idempotency_tag returns the FIRST item whose name contains the tag."""
    tag = "abc123"
    respx.get(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "c1", "name": f"My Campaign [{tag}]", "status": "PAUSED"},
                    {"id": "c2", "name": "Other Campaign", "status": "PAUSED"},
                ]
            },
        )
    )
    result = await client.find_by_idempotency_tag("act_1234", "campaigns", tag)
    assert result is not None
    assert result["id"] == "c1"
    assert tag in result["name"]


@respx.mock
@pytest.mark.asyncio
async def test_find_by_idempotency_tag_returns_none_when_no_match(client: RealMetaWriteClient) -> None:
    respx.get(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "c2", "name": "Other Campaign", "status": "PAUSED"}]},
        )
    )
    result = await client.find_by_idempotency_tag("act_1234", "campaigns", "notfound")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_upload_image_returns_hash(client: RealMetaWriteClient) -> None:
    respx.post(f"{BASE}/act_1234/adimages").mock(
        return_value=httpx.Response(
            200, json={"images": {"test.png": {"hash": "img_hash_abc"}}}
        )
    )
    body, _ = await client.upload_image("act_1234", b"\x89PNG\r\n", "test.png")
    assert body["images"]["test.png"]["hash"] == "img_hash_abc"
