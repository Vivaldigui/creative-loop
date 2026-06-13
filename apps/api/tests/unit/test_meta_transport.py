"""Unit tests for MetaGraphTransport — retry logic, rate-limit detection, write guard."""
from __future__ import annotations

import hashlib
import hmac
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from meta_client.transport import (  # noqa: E402
    MetaAuthError,
    MetaGraphTransport,
    MetaRateLimitError,
    MetaWriteForbiddenError,
)
from meta_client.real import RealMetaClient  # noqa: E402


@pytest.fixture
def transport():
    return MetaGraphTransport(
        access_token="test_token",
        app_secret="test_secret",
        api_version="v21.0",
        max_retries=3,
        min_interval_ms=0,  # no sleep in tests
    )


# ── appsecret_proof ───────────────────────────────────────────────

def test_appsecret_proof_is_hmac_sha256(transport):
    expected = hmac.new(b"test_secret", b"test_token", hashlib.sha256).hexdigest()
    assert transport._appsecret_proof() == expected


# ── Token redaction ───────────────────────────────────────────────

def test_redact_masks_token_and_secret(transport):
    params = {"access_token": "abc123", "appsecret_proof": "xyz", "fields": "id,name"}
    redacted = transport._redact(params)
    assert redacted["access_token"] == "***REDACTED***"
    assert redacted["appsecret_proof"] == "***REDACTED***"
    assert redacted["fields"] == "id,name"


# ── Write guard ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_only_strings_are_accepted_as_paths(transport):
    """Non-string path raises MetaWriteForbiddenError (type safety guard)."""
    with pytest.raises(MetaWriteForbiddenError):
        await transport._get(123, {})  # type: ignore


# ── Successful GET ────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_successful_get_returns_data(transport):
    respx.get("https://graph.facebook.com/v21.0/test").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "1"}]})
    )
    result = await transport.get("test", {})
    assert result["data"][0]["id"] == "1"


@respx.mock
@pytest.mark.asyncio
async def test_request_id_attached(transport):
    respx.get("https://graph.facebook.com/v21.0/test").mock(
        return_value=httpx.Response(
            200,
            json={"data": []},
            headers={"x-fb-request-id": "req_abc123"},
        )
    )
    result = await transport.get("test", {})
    assert result["_request_id"] == "req_abc123"


@respx.mock
@pytest.mark.asyncio
async def test_list_ad_accounts_only_requests_ads_read_fields():
    route = respx.get("https://graph.facebook.com/v21.0/me/adaccounts").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "act_123"}]})
    )
    client = RealMetaClient(
        access_token="test_token",
        app_secret="test_secret",
        api_version="v21.0",
        max_retries=1,
    )

    accounts = await client.list_ad_accounts()

    assert accounts == [{"id": "act_123"}]
    fields = route.calls.last.request.url.params["fields"]
    assert fields == "id,name,currency,timezone_name,account_status"
    assert "business" not in fields


# ── Auth error — no retry ─────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_auth_error_raises_immediately(transport):
    respx.get("https://graph.facebook.com/v21.0/test").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": 190, "message": "Invalid OAuth token"}},
        )
    )
    with pytest.raises(MetaAuthError):
        await transport.get("test", {})


@respx.mock
@pytest.mark.asyncio
async def test_auth_error_not_retried(transport):
    route = respx.get("https://graph.facebook.com/v21.0/test").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": 190, "message": "Invalid OAuth token"}},
        )
    )
    with pytest.raises(MetaAuthError):
        await transport.get("test", {})
    # Auth error should not retry — called exactly once
    assert route.call_count == 1


# ── Rate limit — retries with backoff ────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_rate_limit_retries_then_raises(transport):
    route = respx.get("https://graph.facebook.com/v21.0/test").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": 4, "message": "Application request limit"}},
        )
    )
    with pytest.raises(MetaRateLimitError):
        await transport.get("test", {})
    assert route.call_count == transport._max_retries


# ── 5xx server error — retries ────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_server_error_retries(transport):
    route = respx.get("https://graph.facebook.com/v21.0/test").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )
    with pytest.raises(Exception, match="503"):
        await transport.get("test", {})
    assert route.call_count == transport._max_retries


# ── Eventual success after transient errors ───────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_succeeds_after_transient_failure(transport):
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return httpx.Response(503, text="tmp error")
        return httpx.Response(200, json={"data": [{"id": "ok"}]})

    respx.get("https://graph.facebook.com/v21.0/test").mock(side_effect=side_effect)
    result = await transport.get("test", {})
    assert result["data"][0]["id"] == "ok"
    assert call_count == 2


# ── Pagination ────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_paginate_follows_cursor(transport):
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={
                "data": [{"id": "a"}, {"id": "b"}],
                "paging": {"cursors": {"after": "cursor_2"}, "next": "http://..."},
            })
        return httpx.Response(200, json={
            "data": [{"id": "c"}],
            "paging": {},
        })

    respx.get("https://graph.facebook.com/v21.0/things").mock(side_effect=side_effect)
    items = []
    async for item in transport.paginate("things", {}):
        items.append(item)
    assert [i["id"] for i in items] == ["a", "b", "c"]
    assert call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_paginate_stops_on_duplicate_cursor(transport):
    """Infinite loop guard: same cursor repeated → stop."""
    respx.get("https://graph.facebook.com/v21.0/things").mock(
        return_value=httpx.Response(200, json={
            "data": [{"id": "x"}],
            "paging": {"cursors": {"after": "same_cursor"}, "next": "http://..."},
        })
    )
    items = []
    async for item in transport.paginate("things", {}):
        items.append(item)
        if len(items) > 10:
            break
    # Should stop after second page sees same cursor
    assert len(items) <= 2
