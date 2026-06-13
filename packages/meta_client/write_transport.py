"""
WriteGraphTransport — POST/multipart client for Meta Marketing API.

Strictly separate from MetaGraphTransport (read-only GET).
The read client's GET-only guarantee is preserved by keeping write
operations in this dedicated module.

Retry policy (enforced here):
  Safe/idempotent:  validate_token, get_node, upload_image (Meta dedupes by hash),
                    update_status→PAUSE, GET status.  → up to meta_write_max_retries
  Non-idempotent:   create_campaign/adset/creative/ad, update_status→ACTIVE.
                    → NO automatic retry.  The RealPublisher handles reconciliation.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# ── Error code classification (same taxonomy as read transport) ─────────────
_AUTH_ERROR_CODES = {190, 102, 10, 200, 803}
_RATE_LIMIT_CODES = {4, 17, 32, 613, 80000, 80004}
_RETRIABLE_HTTP = {500, 502, 503, 504}

_SENSITIVE_KEYS = frozenset({"token", "secret", "proof", "password", "key"})

_BASE_URL = "https://graph.facebook.com"


# ── Typed exceptions ────────────────────────────────────────────────────────

class MetaWriteAuthError(Exception):
    """Non-retryable: invalid/expired token or missing permission."""
    def __init__(self, msg: str, code: int = 0, request_id: str = "") -> None:
        super().__init__(msg)
        self.code = code
        self.request_id = request_id


class MetaWriteRateLimitError(Exception):
    """Rate limit hit after all retries."""
    def __init__(self, msg: str, request_id: str = "") -> None:
        super().__init__(msg)
        self.request_id = request_id


class MetaWritePermissionError(Exception):
    """Missing ad account permission or scope."""
    def __init__(self, msg: str, code: int = 0, request_id: str = "") -> None:
        super().__init__(msg)
        self.code = code
        self.request_id = request_id


class MetaWritePolicyRejectionError(Exception):
    """Content/policy rejection from Meta — not retryable, ad is disapproved."""
    def __init__(self, msg: str, code: int = 0, subcode: int = 0, request_id: str = "") -> None:
        super().__init__(msg)
        self.code = code
        self.subcode = subcode
        self.request_id = request_id


class MetaWriteAmbiguousError(Exception):
    """
    Timeout or network error AFTER sending a non-idempotent request.
    The resource may or may not have been created.  Must reconcile before retrying.
    """
    def __init__(self, msg: str, request_id: str = "") -> None:
        super().__init__(msg)
        self.request_id = request_id


class MetaWriteTransientError(Exception):
    """Server error or transient network failure — retryable for idempotent ops."""
    def __init__(self, msg: str, status: int = 0, request_id: str = "") -> None:
        super().__init__(msg)
        self.http_status = status
        self.request_id = request_id


# ── Transport ───────────────────────────────────────────────────────────────

class WriteGraphTransport:
    """
    Authenticated POST/GET write transport for Meta Marketing API.

    Security guarantees:
      - access_token and appsecret_proof never appear in logs.
      - Caller is responsible for choosing retry vs no-retry per operation.
      - x-fb-request-id captured on every response (success and error).
    """

    def __init__(
        self,
        access_token: str,
        app_secret: str,
        api_version: str = "v21.0",
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ) -> None:
        self._token = access_token
        self._app_secret = app_secret
        self._version = api_version
        self._base = f"{_BASE_URL}/{api_version}"
        self._max_retries = max_retries
        self._timeout = timeout_s

    # ── Public methods ────────────────────────────────────────────

    async def get(self, path: str, params: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Authenticated GET. Returns (body, request_id). Retryable."""
        url = self._url(path)
        return await self._get_with_retry(url, params)

    async def post(
        self,
        path: str,
        data: dict[str, Any],
        *,
        idempotent: bool = False,
    ) -> tuple[dict[str, Any], str]:
        """
        POST form-encoded data. Returns (body, request_id).

        idempotent=True enables automatic retries (e.g., PAUSE status update).
        idempotent=False (default): raises MetaWriteAmbiguousError on timeout/5xx
        AFTER the request was sent, so the caller can reconcile.
        """
        url = self._url(path)
        return await self._post_with_policy(url, data, idempotent=idempotent)

    async def post_multipart(
        self,
        path: str,
        fields: dict[str, Any],
        file_bytes: bytes,
        filename: str,
    ) -> tuple[dict[str, Any], str]:
        """
        POST multipart/form-data (image upload).
        Image upload is effectively idempotent via Meta's hash deduplication.
        """
        url = self._url(path)
        return await self._post_multipart_with_retry(url, fields, file_bytes, filename)

    # ── URL builder ───────────────────────────────────────────────

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self._base}/{path.lstrip('/')}"

    # ── Auth helpers ──────────────────────────────────────────────

    def _appsecret_proof(self) -> str:
        return hmac.new(
            self._app_secret.encode(),
            self._token.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _auth_params(self) -> dict[str, str]:
        return {
            "access_token": self._token,
            "appsecret_proof": self._appsecret_proof(),
        }

    @staticmethod
    def _redact(d: dict[str, Any]) -> dict[str, Any]:
        return {
            k: "***REDACTED***" if any(s in k.lower() for s in _SENSITIVE_KEYS) else v
            for k, v in d.items()
        }

    # ── GET with retry ────────────────────────────────────────────

    async def _get_with_retry(
        self, url: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        full_params = {**self._auth_params(), **params}
        last_exc: Exception = Exception("max retries exhausted")
        for attempt in range(self._max_retries):
            if attempt:
                await asyncio.sleep(self._backoff(attempt))
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url, params=full_params)
                    request_id = resp.headers.get("x-fb-request-id", "")
                    body, exc = self._parse_response(resp, request_id)
                    if exc is None:
                        return body, request_id
                    if isinstance(exc, (MetaWriteAuthError, MetaWritePermissionError,
                                        MetaWritePolicyRejectionError)):
                        raise exc
                    last_exc = exc
                    continue
            except (MetaWriteAuthError, MetaWritePermissionError,
                    MetaWritePolicyRejectionError):
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.warning("meta_write_get_network_error", url=url, attempt=attempt, error=str(exc))
                last_exc = exc
        raise last_exc

    # ── POST with policy ──────────────────────────────────────────

    async def _post_with_policy(
        self,
        url: str,
        data: dict[str, Any],
        *,
        idempotent: bool,
    ) -> tuple[dict[str, Any], str]:
        full_data = {**self._auth_params(), **data}
        last_exc: Exception = Exception("max retries exhausted")
        retries = self._max_retries if idempotent else 1

        for attempt in range(retries):
            if attempt:
                await asyncio.sleep(self._backoff(attempt))
            sent = False
            request_id = ""
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, data=full_data)
                    sent = True
                    request_id = resp.headers.get("x-fb-request-id", "")
                    body, exc = self._parse_response(resp, request_id)
                    if exc is None:
                        return body, request_id
                    if isinstance(exc, (MetaWriteAuthError, MetaWritePermissionError,
                                        MetaWritePolicyRejectionError)):
                        raise exc
                    if not idempotent:
                        raise MetaWriteAmbiguousError(
                            f"Non-idempotent POST failed after send: {exc}", request_id=request_id
                        )
                    last_exc = exc
                    continue
            except (MetaWriteAuthError, MetaWritePermissionError,
                    MetaWritePolicyRejectionError):
                raise
            except MetaWriteAmbiguousError:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if sent and not idempotent:
                    raise MetaWriteAmbiguousError(
                        f"Network error after sending non-idempotent POST: {exc}",
                        request_id=request_id,
                    ) from exc
                logger.warning("meta_write_post_network_error", url=url, attempt=attempt, error=str(exc))
                last_exc = exc
        raise last_exc

    # ── Multipart POST with retry ─────────────────────────────────

    async def _post_multipart_with_retry(
        self,
        url: str,
        fields: dict[str, Any],
        file_bytes: bytes,
        filename: str,
    ) -> tuple[dict[str, Any], str]:
        auth = self._auth_params()
        last_exc: Exception = Exception("max retries exhausted")
        for attempt in range(self._max_retries):
            if attempt:
                await asyncio.sleep(self._backoff(attempt))
            try:
                async with httpx.AsyncClient(timeout=max(self._timeout, 120.0)) as client:
                    resp = await client.post(
                        url,
                        data={**auth, **fields},
                        files={"filename": (filename, file_bytes, "image/png")},
                    )
                    request_id = resp.headers.get("x-fb-request-id", "")
                    body, exc = self._parse_response(resp, request_id)
                    if exc is None:
                        return body, request_id
                    if isinstance(exc, (MetaWriteAuthError, MetaWritePermissionError)):
                        raise exc
                    last_exc = exc
                    continue
            except (MetaWriteAuthError, MetaWritePermissionError):
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.warning("meta_write_multipart_network_error", attempt=attempt, error=str(exc))
                last_exc = exc
        raise last_exc

    # ── Response parser ───────────────────────────────────────────

    def _parse_response(
        self,
        resp: httpx.Response,
        request_id: str,
    ) -> tuple[dict[str, Any], Exception | None]:
        """
        Returns (body, None) on success, or (body, exception) on error.
        Never raises directly — caller decides whether to raise or retry.
        """
        self._inspect_usage(resp.headers)

        if resp.status_code == 200:
            try:
                body = resp.json()
                body["_request_id"] = request_id
                return body, None
            except Exception:
                return {}, MetaWriteTransientError(
                    "Could not parse JSON from 200 response", status=200, request_id=request_id
                )

        # Parse error body
        try:
            err_body = resp.json()
            err = err_body.get("error", {})
            code = int(err.get("code", 0))
            subcode = int(err.get("error_subcode", 0))
            message = err.get("message", "")
            fbtrace = err.get("fbtrace_id", "")
        except Exception:
            code, subcode, message, fbtrace = 0, 0, resp.text[:200], ""

        log = logger.bind(
            request_id=request_id,
            code=code,
            subcode=subcode,
            status=resp.status_code,
            fbtrace=fbtrace,
        )

        if code in _AUTH_ERROR_CODES:
            log.warning("meta_write_auth_error", message=message)
            return {}, MetaWriteAuthError(f"Auth error {code}: {message}", code=code, request_id=request_id)

        if code in _RATE_LIMIT_CODES or resp.status_code == 429:
            log.warning("meta_write_rate_limit", message=message)
            return {}, MetaWriteRateLimitError(
                f"Rate limit code={code}: {message}", request_id=request_id
            )

        # Policy/content rejection codes (1487xxx, 1815xxx, etc.)
        if 1_400_000 <= code < 2_000_000 or subcode in {1487655, 1487390, 1488068}:
            log.warning("meta_write_policy_rejection", message=message, code=code, subcode=subcode)
            return {}, MetaWritePolicyRejectionError(
                f"Policy rejection {code}/{subcode}: {message}",
                code=code, subcode=subcode, request_id=request_id,
            )

        # Permission errors
        if code == 200 or resp.status_code == 403:
            log.warning("meta_write_permission_error", message=message)
            return {}, MetaWritePermissionError(
                f"Permission error {code}: {message}", code=code, request_id=request_id
            )

        if resp.status_code in _RETRIABLE_HTTP:
            log.warning("meta_write_server_error", message=message)
            return {}, MetaWriteTransientError(
                f"HTTP {resp.status_code}: {message}", status=resp.status_code, request_id=request_id
            )

        log.error("meta_write_unexpected_error", message=message)
        return {}, MetaWriteTransientError(
            f"Unexpected HTTP {resp.status_code} code={code}: {message}",
            status=resp.status_code, request_id=request_id,
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _backoff(self, attempt: int) -> float:
        base = min(2.0 ** attempt, 60.0)
        return base * (0.5 + random.random() * 0.5)

    def _inspect_usage(self, headers: httpx.Headers) -> None:
        for header in ("x-business-use-case-usage", "x-app-usage", "x-ad-account-usage"):
            raw = headers.get(header)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    for key, entries in data.items():
                        if not isinstance(entries, list):
                            continue
                        for entry in entries:
                            for metric in ("call_count", "total_time", "total_cputime"):
                                pct = entry.get(metric, 0)
                                if isinstance(pct, (int, float)) and pct > 85:
                                    logger.warning(
                                        "meta_write_approaching_rate_limit",
                                        header=header, key=key, metric=metric, pct=pct,
                                    )
            except Exception:
                pass
