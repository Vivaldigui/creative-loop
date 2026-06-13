"""
RealMetaWriteClient — Phase 6 write client for Meta Marketing API.

Security model:
  - Status is enforced PAUSED at the DTO layer (frozen field, _force_paused validator).
  - This client asserts PAUSED before every create_ad call.
  - Non-idempotent creates do NOT auto-retry; caller handles reconciliation.
  - Tokens are never logged (WriteGraphTransport redacts them).
  - update_ad_status("ACTIVE") is callable but deliberately not invoked by any
    automated path — only the manual activation endpoint calls it.
"""
from __future__ import annotations

from typing import Any

import structlog

from packages.meta_client.write_transport import (
    WriteGraphTransport,
)

logger = structlog.get_logger()

# Retained for backwards compatibility so tests that import the old stub still pass.
class MetaPublishDisabledError(Exception):
    """Raised by the Phase 5 stub. No longer raised in Phase 6 real client."""


_REQUIRED_WRITE_SCOPES = {"ads_management", "ads_read"}


class RealMetaWriteClient:
    """
    Real write client for Meta Marketing API.

    All create_* methods are non-idempotent — they do NOT auto-retry on failure.
    Callers MUST handle reconciliation if a request fails after being sent.

    upload_image and pause (ACTIVE→PAUSED) are idempotent and auto-retry.
    """

    def __init__(
        self,
        access_token: str,
        app_secret: str,
        api_version: str = "v21.0",
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ) -> None:
        self._transport = WriteGraphTransport(
            access_token=access_token,
            app_secret=app_secret,
            api_version=api_version,
            max_retries=max_retries,
            timeout_s=timeout_s,
        )
        self._version = api_version

    # ── Credential / health ───────────────────────────────────────

    async def validate_token(self, account_id: str) -> dict[str, Any]:
        """
        Validate the token against /me and the ad account.
        Returns {'valid': bool, 'user_id': str, 'account_accessible': bool, 'scopes': list}.
        Never raises on auth failure — returns {'valid': False, 'error': ...}.
        """
        try:
            me_body, req_id = await self._transport.get("me", {"fields": "id,name"})
            user_id = me_body.get("id", "")
            account_id_clean = account_id.lstrip("act_")
            acc_body, _ = await self._transport.get(
                f"act_{account_id_clean}",
                {"fields": "id,name,account_status"},
            )
            accessible = bool(acc_body.get("id"))
            return {
                "valid": True,
                "user_id": user_id,
                "account_accessible": accessible,
                "account_status": acc_body.get("account_status"),
                "request_id": req_id,
            }
        except Exception as exc:
            logger.warning("meta_validate_token_failed", error=str(exc))
            return {"valid": False, "error": str(exc)}

    # ── Image upload ──────────────────────────────────────────────

    async def upload_image(
        self, account_id: str, image_bytes: bytes, filename: str
    ) -> tuple[dict[str, Any], str]:
        """
        Upload image bytes to /{account_id}/adimages.
        Returns (body, request_id).
        Idempotent: Meta deduplicates by image hash.
        """
        account_id_clean = account_id.lstrip("act_")
        body, req_id = await self._transport.post_multipart(
            f"act_{account_id_clean}/adimages",
            fields={},
            file_bytes=image_bytes,
            filename=filename,
        )
        logger.info("meta_image_uploaded", filename=filename, request_id=req_id)
        return body, req_id

    # ── Campaign ──────────────────────────────────────────────────

    async def create_campaign(
        self, account_id: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """
        POST /{account_id}/campaigns. Non-idempotent — no auto-retry.
        payload['status'] must be 'PAUSED' (enforced by caller DTO).
        Returns (body, request_id).
        """
        assert payload.get("status") == "PAUSED", "Campaign must be created PAUSED"
        account_id_clean = account_id.lstrip("act_")
        body, req_id = await self._transport.post(
            f"act_{account_id_clean}/campaigns",
            payload,
            idempotent=False,
        )
        logger.info("meta_campaign_created", campaign_id=body.get("id"), request_id=req_id)
        return body, req_id

    # ── Ad set ────────────────────────────────────────────────────

    async def create_adset(
        self, account_id: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """POST /{account_id}/adsets. Non-idempotent — no auto-retry."""
        assert payload.get("status") == "PAUSED", "AdSet must be created PAUSED"
        account_id_clean = account_id.lstrip("act_")
        body, req_id = await self._transport.post(
            f"act_{account_id_clean}/adsets",
            payload,
            idempotent=False,
        )
        logger.info("meta_adset_created", adset_id=body.get("id"), request_id=req_id)
        return body, req_id

    # ── Ad creative ───────────────────────────────────────────────

    async def create_ad_creative(
        self, account_id: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """POST /{account_id}/adcreatives. Non-idempotent — no auto-retry."""
        account_id_clean = account_id.lstrip("act_")
        body, req_id = await self._transport.post(
            f"act_{account_id_clean}/adcreatives",
            payload,
            idempotent=False,
        )
        logger.info("meta_ad_creative_created", creative_id=body.get("id"), request_id=req_id)
        return body, req_id

    # ── Ad ────────────────────────────────────────────────────────

    async def create_ad(
        self, account_id: str, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """
        POST /{account_id}/ads. Non-idempotent — no auto-retry.
        CRITICAL: asserts status == PAUSED before sending.
        """
        if payload.get("status") != "PAUSED":
            raise ValueError(
                f"Refusing to create ad with status={payload.get('status')!r}. "
                "All ads must be created PAUSED."
            )
        account_id_clean = account_id.lstrip("act_")
        body, req_id = await self._transport.post(
            f"act_{account_id_clean}/ads",
            payload,
            idempotent=False,
        )
        logger.info("meta_ad_created", ad_id=body.get("id"), request_id=req_id, status="PAUSED")
        return body, req_id

    # ── Status management ─────────────────────────────────────────

    async def get_status(self, node_id: str) -> tuple[dict[str, Any], str]:
        """
        GET /{node_id}?fields=effective_status,configured_status,status.
        Idempotent, auto-retried.
        """
        body, req_id = await self._transport.get(
            node_id,
            {"fields": "id,effective_status,configured_status,status,name"},
        )
        return body, req_id

    async def update_ad_status(
        self, ad_id: str, new_status: str
    ) -> tuple[dict[str, Any], str]:
        """
        POST /{ad_id} with status=new_status.

        ACTIVE: non-idempotent by intent (deliberate activation) — single attempt.
        PAUSED: idempotent (safe to retry — pausing a paused ad is a no-op).
        """
        if new_status not in ("ACTIVE", "PAUSED", "DELETED", "ARCHIVED"):
            raise ValueError(f"Invalid ad status: {new_status!r}")
        idempotent = new_status != "ACTIVE"
        body, req_id = await self._transport.post(
            ad_id,
            {"status": new_status},
            idempotent=idempotent,
        )
        logger.info("meta_ad_status_updated", ad_id=ad_id, status=new_status, request_id=req_id)
        return body, req_id

    async def update_budget(
        self, adset_id: str, daily_budget: int
    ) -> tuple[dict[str, Any], str]:
        """POST /{adset_id} with daily_budget. Reserved for Phase 7."""
        raise NotImplementedError("Budget updates are reserved for Phase 7.")

    # ── Reconciliation helper ─────────────────────────────────────

    async def find_by_idempotency_tag(
        self,
        account_id: str,
        resource_type: str,
        tag: str,
    ) -> dict[str, Any] | None:
        """
        Search for a previously created resource by the idempotency tag injected
        into its name.  Returns the first match or None.

        resource_type: "campaigns" | "adsets" | "ads" | "adcreatives"
        """
        account_id_clean = account_id.lstrip("act_")
        try:
            body, _ = await self._transport.get(
                f"act_{account_id_clean}/{resource_type}",
                {"fields": "id,name,status,effective_status", "limit": "50"},
            )
            items = body.get("data", [])
            for item in items:
                if tag in (item.get("name") or ""):
                    return item
        except Exception as exc:
            logger.warning(
                "meta_reconcile_search_failed",
                resource_type=resource_type, tag=tag, error=str(exc),
            )
        return None
