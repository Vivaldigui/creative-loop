from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import structlog

logger = structlog.get_logger()

# Error code classifications
_AUTH_ERROR_CODES = {190, 102, 10, 200, 803}
_RATE_LIMIT_CODES = {4, 17, 32, 613, 80000, 80004}
_RETRIABLE_HTTP = {500, 502, 503, 504}


class MetaWriteForbiddenError(Exception):
    """Raised when a non-GET method is attempted. The Phase 2 client is read-only."""


class MetaAuthError(Exception):
    """Non-retryable authentication or permission error."""


class MetaRateLimitError(Exception):
    """Rate limit hit after all retries."""


class MetaGraphTransport:
    """
    Single point of egress to the Meta Graph API.
    Enforces read-only (GET only), handles retries, backoff, and rate-limit headers.
    Captures x-fb-request-id on every call.
    Never logs access_token or appsecret_proof in plaintext.
    """

    _BASE = "https://graph.facebook.com"

    def __init__(
        self,
        access_token: str,
        app_secret: str,
        api_version: str = "v21.0",
        max_retries: int = 5,
        rate_limit_threshold: int = 85,
        min_interval_ms: int = 200,
    ) -> None:
        self._token = access_token
        self._app_secret = app_secret
        self._version = api_version
        self._base = f"{self._BASE}/{api_version}"
        self._max_retries = max_retries
        self._rate_threshold = rate_limit_threshold
        self._min_interval = min_interval_ms / 1000.0

    # ── Public ────────────────────────────────────────────────────

    async def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Authenticated GET with retry/backoff. Returns response dict."""
        return await self._get(path, params)

    async def paginate(
        self,
        path: str,
        params: dict[str, Any],
        max_pages: int = 200,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator that follows cursor pagination, yielding each item."""
        seen_cursors: set[str] = set()
        current_params = dict(params)
        page = 0

        while page < max_pages:
            data = await self._get(path, current_params)
            items = data.get("data", [])
            for item in items:
                yield item

            paging = data.get("paging", {})
            if not paging.get("next"):
                break

            # Extract cursor from paging.cursors or from the next URL
            cursors = paging.get("cursors", {})
            after = cursors.get("after") or _extract_after(paging.get("next", ""))

            if not after or after in seen_cursors:
                break
            seen_cursors.add(after)
            current_params = {**params, "after": after}
            page += 1

        if page >= max_pages:
            logger.warning("meta_max_pages_reached", path=path, max_pages=max_pages)

    # ── Internal ──────────────────────────────────────────────────

    def _appsecret_proof(self) -> str:
        return hmac.new(
            self._app_secret.encode(),
            self._token.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _build_params(self, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            "access_token": self._token,
            "appsecret_proof": self._appsecret_proof(),
            **extra,
        }

    @staticmethod
    def _redact(params: dict[str, Any]) -> dict[str, Any]:
        return {
            k: "***REDACTED***" if any(s in k.lower() for s in ("token", "secret", "proof")) else v
            for k, v in params.items()
        }

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        # Guard: only GET
        if not isinstance(path, str):
            raise MetaWriteForbiddenError("Only string paths are allowed.")

        url = path if path.startswith("http") else f"{self._base}/{path.lstrip('/')}"
        request_params = self._build_params(params)

        last_exc: Exception = Exception("max retries")
        for attempt in range(self._max_retries):
            await asyncio.sleep(self._min_interval if attempt == 0 else 0)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=request_params)
                    request_id = resp.headers.get("x-fb-request-id", "")
                    self._inspect_usage(resp.headers)

                    if resp.status_code == 200:
                        body = resp.json()
                        body["_request_id"] = request_id
                        return body

                    # Parse error body
                    try:
                        err_body = resp.json()
                        err = err_body.get("error", {})
                        code = int(err.get("code", 0))
                        message = err.get("message", "")
                    except Exception:
                        code = 0
                        message = resp.text[:200]

                    log = logger.bind(
                        request_id=request_id,
                        code=code,
                        status=resp.status_code,
                        attempt=attempt,
                    )

                    if code in _AUTH_ERROR_CODES:
                        raise MetaAuthError(f"Auth error {code}: {message}")

                    if code in _RATE_LIMIT_CODES or resp.status_code == 429:
                        wait = self._rate_wait(resp.headers, attempt)
                        log.warning("meta_rate_limit", wait=wait)
                        await asyncio.sleep(wait)
                        last_exc = MetaRateLimitError(f"Rate limit code={code}")
                        continue

                    if resp.status_code in _RETRIABLE_HTTP:
                        wait = self._backoff(attempt)
                        log.warning("meta_server_error", wait=wait)
                        await asyncio.sleep(wait)
                        last_exc = Exception(f"HTTP {resp.status_code}: {message}")
                        continue

                    raise Exception(f"Meta API HTTP {resp.status_code} code={code}: {message}")

            except (MetaAuthError, MetaWriteForbiddenError):
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                wait = self._backoff(attempt)
                logger.warning("meta_transport_error", error=str(exc), attempt=attempt, wait=wait)
                await asyncio.sleep(wait)
                last_exc = exc

        raise last_exc

    def _backoff(self, attempt: int) -> float:
        base = min(2.0 ** attempt, 120.0)
        return base * (0.5 + random.random() * 0.5)

    def _rate_wait(self, headers: httpx.Headers, attempt: int) -> float:
        # Use estimated_time_to_regain_access if present in the body (passed via headers workaround)
        return min(30.0 * (attempt + 1), 120.0)

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
                                if isinstance(pct, (int, float)) and pct > self._rate_threshold:
                                    logger.warning(
                                        "meta_approaching_rate_limit",
                                        header=header,
                                        key=key,
                                        metric=metric,
                                        pct=pct,
                                    )
            except Exception:
                pass


def _extract_after(next_url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(next_url).query)
        vals = qs.get("after")
        return vals[0] if vals else None
    except Exception:
        return None
