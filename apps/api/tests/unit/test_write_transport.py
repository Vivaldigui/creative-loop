"""
Unit tests for WriteGraphTransport.

Uses respx to mock httpx calls — no real HTTP.
Tests cover: auth errors, rate limit, permission, policy rejection, token redaction.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest
import respx
from packages.meta_client.write_transport import (
    MetaWriteAuthError,
    MetaWritePermissionError,
    MetaWritePolicyRejectionError,
    MetaWriteRateLimitError,
    WriteGraphTransport,
)

BASE = "https://graph.facebook.com/v21.0"


@pytest.fixture
def transport() -> WriteGraphTransport:
    return WriteGraphTransport(
        access_token="test_token",
        app_secret="test_secret",
        api_version="v21.0",
        max_retries=2,
        timeout_s=5.0,
    )


# ── appsecret_proof ──────────────────────────────────────────────────────────

def test_appsecret_proof_is_hmac_sha256(transport: WriteGraphTransport) -> None:
    expected = hmac.new(b"test_secret", b"test_token", hashlib.sha256).hexdigest()
    assert transport._appsecret_proof() == expected


def test_redact_masks_sensitive_keys(transport: WriteGraphTransport) -> None:
    params = {"access_token": "abc", "appsecret_proof": "xyz", "fields": "id,name", "key": "secret"}
    redacted = transport._redact(params)
    assert redacted["access_token"] == "***REDACTED***"
    assert redacted["appsecret_proof"] == "***REDACTED***"
    assert redacted["key"] == "***REDACTED***"
    assert redacted["fields"] == "id,name"


# ── GET ───────────────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_success(transport: WriteGraphTransport) -> None:
    respx.get(f"{BASE}/ad_123").mock(
        return_value=httpx.Response(
            200,
            json={"id": "ad_123", "effective_status": "PAUSED"},
            headers={"x-fb-request-id": "req-abc"},
        )
    )
    body, req_id = await transport.get("ad_123", {"fields": "id,effective_status"})
    assert body["id"] == "ad_123"
    assert req_id == "req-abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_auth_error(transport: WriteGraphTransport) -> None:
    respx.get(f"{BASE}/ad_123").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": 190, "type": "OAuthException", "message": "Invalid token"}},
        )
    )
    with pytest.raises(MetaWriteAuthError):
        await transport.get("ad_123", {"fields": "id"})


# ── POST ──────────────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_post_success_captures_request_id(transport: WriteGraphTransport) -> None:
    respx.post(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            200,
            json={"id": "camp_new"},
            headers={"x-fb-request-id": "req-xyz"},
        )
    )
    body, req_id = await transport.post("act_1234/campaigns", {"name": "Test"}, idempotent=False)
    assert body["id"] == "camp_new"
    assert req_id == "req-xyz"


@respx.mock
@pytest.mark.asyncio
async def test_post_auth_error_raises(transport: WriteGraphTransport) -> None:
    respx.post(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"code": 190, "type": "OAuthException", "message": "Bad token"}},
        )
    )
    with pytest.raises(MetaWriteAuthError):
        await transport.post("act_1234/campaigns", {"name": "Test"}, idempotent=False)


@respx.mock
@pytest.mark.asyncio
async def test_post_rate_limit_on_idempotent_raises(transport: WriteGraphTransport) -> None:
    """For idempotent ops, rate limit after all retries raises MetaWriteRateLimitError."""
    respx.post(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            429,
            json={"error": {"code": 17, "type": "OAuthException", "message": "Call limit"}},
        )
    )
    with pytest.raises(MetaWriteRateLimitError):
        await transport.post("act_1234/campaigns", {"name": "Test"}, idempotent=True)


@respx.mock
@pytest.mark.asyncio
async def test_post_permission_error_raises(transport: WriteGraphTransport) -> None:
    # Use code 0 so auth_error check doesn't fire first; HTTP 403 triggers permission branch
    respx.post(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            403,
            json={"error": {"code": 0, "type": "GraphMethodException", "message": "No permission"}},
        )
    )
    with pytest.raises(MetaWritePermissionError):
        await transport.post("act_1234/campaigns", {"name": "Test"}, idempotent=False)


@respx.mock
@pytest.mark.asyncio
async def test_post_policy_rejection_raises(transport: WriteGraphTransport) -> None:
    respx.post(f"{BASE}/act_1234/campaigns").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": 1487070, "type": "OAuthException", "message": "Policy violation"}},
        )
    )
    with pytest.raises(MetaWritePolicyRejectionError):
        await transport.post("act_1234/campaigns", {"name": "Test"}, idempotent=False)
