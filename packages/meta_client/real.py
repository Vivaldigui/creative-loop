from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import structlog

from .transport import MetaGraphTransport

logger = structlog.get_logger()

_CAMPAIGN_FIELDS = (
    "id,name,objective,effective_status,configured_status,"
    "buying_type,daily_budget,lifetime_budget,start_time,stop_time"
)
_ADSET_FIELDS = (
    "id,name,campaign_id,optimization_goal,billing_event,bid_strategy,"
    "targeting,daily_budget,lifetime_budget,effective_status,start_time,end_time"
)
_AD_FIELDS = (
    "id,name,adset_id,campaign_id,effective_status,configured_status,"
    "creative{id,name,title,body,call_to_action_type,link_url,"
    "image_hash,image_url,thumbnail_url,object_story_spec}"
)
_IMAGE_FIELDS = "hash,name,url,width,height,bytes,created_time"
_INSIGHT_FIELDS = (
    "impressions,reach,frequency,spend,clicks,inline_link_clicks,"
    "ctr,cpc,cpm,account_currency,attribution_setting,"
    "actions,action_values,purchase_roas,"
    "ad_id,ad_name,adset_id,campaign_id,date_start,date_stop"
)


class RealMetaClient:
    """
    Read-only Meta Marketing API client (Phase 2+).
    All iteration methods are async generators.
    No write methods exist; publish_dry_run raises NotImplementedError.
    """

    def __init__(
        self,
        access_token: str,
        app_secret: str,
        api_version: str = "v21.0",
        page_limit: int = 200,
        max_retries: int = 5,
        rate_limit_threshold: int = 85,
    ) -> None:
        self._transport = MetaGraphTransport(
            access_token=access_token,
            app_secret=app_secret,
            api_version=api_version,
            max_retries=max_retries,
            rate_limit_threshold=rate_limit_threshold,
        )
        self._page_limit = page_limit

    # ── Auth ────────────────────────────────────────────────────

    async def validate_credentials(self) -> bool:
        try:
            data = await self._transport.get("me", {"fields": "id,name"})
            return bool(data.get("id"))
        except Exception as exc:
            logger.warning("meta_validate_failed", error=str(exc))
            return False

    async def health_check(self) -> bool:
        return await self.validate_credentials()

    async def list_ad_accounts(self) -> list[dict[str, Any]]:
        data = await self._transport.get(
            "me/adaccounts",
            {"fields": "id,name,currency,timezone_name,account_status"},
        )
        return data.get("data", [])

    # ── Campaigns ────────────────────────────────────────────────

    async def iter_campaigns(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self._transport.paginate(
            f"{_norm_account(account_id)}/campaigns",
            {"fields": fields or _CAMPAIGN_FIELDS, "limit": self._page_limit},
        ):
            yield item

    # ── Ad sets ──────────────────────────────────────────────────

    async def iter_adsets(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self._transport.paginate(
            f"{_norm_account(account_id)}/adsets",
            {"fields": fields or _ADSET_FIELDS, "limit": self._page_limit},
        ):
            yield item

    # ── Ads ──────────────────────────────────────────────────────

    async def iter_ads(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self._transport.paginate(
            f"{_norm_account(account_id)}/ads",
            {"fields": fields or _AD_FIELDS, "limit": self._page_limit},
        ):
            yield item

    # ── Images ──────────────────────────────────────────────────

    async def iter_ad_images(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for item in self._transport.paginate(
            f"{_norm_account(account_id)}/adimages",
            {"fields": fields or _IMAGE_FIELDS, "limit": self._page_limit},
        ):
            yield item

    # ── Insights ────────────────────────────────────────────────

    async def iter_insights(
        self,
        account_id: str,
        level: str = "ad",
        date_start: str = "",
        date_stop: str = "",
        fields: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Fetches insights using synchronous GET with time_range.
        Chunks long date ranges monthly to avoid async report jobs
        (which would require POST and polling).
        """
        import json as _json

        if date_start and date_stop:
            chunks = _monthly_chunks(date_start, date_stop)
        else:
            chunks = [(date_start, date_stop)]

        for chunk_start, chunk_stop in chunks:
            params: dict[str, Any] = {
                "fields": fields or _INSIGHT_FIELDS,
                "level": level,
                "limit": self._page_limit,
            }
            if chunk_start and chunk_stop:
                params["time_range"] = _json.dumps(
                    {"since": chunk_start, "until": chunk_stop}
                )
            if extra_params:
                params.update(extra_params)

            async for item in self._transport.paginate(
                f"{_norm_account(account_id)}/insights",
                params,
            ):
                yield item

    # ── No writes allowed ────────────────────────────────────────

    async def publish_dry_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            "RealMetaClient.publish_dry_run is intentionally unimplemented in Phase 2. "
            "Write operations are only available in Phase 6 via a separate write client."
        )


# ── Helpers ───────────────────────────────────────────────────────

def _norm_account(account_id: str) -> str:
    """Ensure account_id has act_ prefix."""
    return account_id if account_id.startswith("act_") else f"act_{account_id}"


def _monthly_chunks(date_start: str, date_stop: str) -> list[tuple[str, str]]:
    """Split date range into monthly chunks (max 31 days each)."""
    from datetime import date, timedelta

    try:
        start = date.fromisoformat(date_start)
        stop = date.fromisoformat(date_stop)
    except ValueError:
        return [(date_start, date_stop)]

    chunks: list[tuple[str, str]] = []
    cursor = start
    while cursor <= stop:
        # End of current month
        if cursor.month == 12:
            end = date(cursor.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(cursor.year, cursor.month + 1, 1) - timedelta(days=1)
        chunk_end = min(end, stop)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks
