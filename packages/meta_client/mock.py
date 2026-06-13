from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class MockMetaClient:
    """
    Mock Meta client — all data from fixtures, no real API calls.
    All yielded items include source="mock" and a fictitious flag.
    publish_dry_run returns a simulated response.
    """

    def __init__(self, fixture_dir: str | Path | None = None) -> None:
        self._dir = Path(fixture_dir) if fixture_dir else FIXTURE_DIR

    def _load(self, filename: str) -> dict[str, Any]:
        path = self._dir / filename
        if not path.exists():
            return {"data": []}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ── Auth ────────────────────────────────────────────────────

    async def validate_credentials(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    async def list_ad_accounts(self) -> list[dict[str, Any]]:
        data = self._load("adaccounts.json")
        return data.get("data", [])

    # ── Campaigns ────────────────────────────────────────────────

    async def iter_campaigns(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        data = self._load("campaigns.json")
        for item in data.get("data", []):
            yield item

    # ── Ad sets ──────────────────────────────────────────────────

    async def iter_adsets(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        data = self._load("adsets.json")
        for item in data.get("data", []):
            yield item

    # ── Ads ──────────────────────────────────────────────────────

    async def iter_ads(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        data = self._load("ads.json")
        for item in data.get("data", []):
            yield item

    # ── Images ──────────────────────────────────────────────────

    async def iter_ad_images(
        self,
        account_id: str,
        fields: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        data = self._load("adimages.json")
        for item in data.get("data", []):
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
        data = self._load("insights.json")
        for item in data.get("data", []):
            # Overlay requested date range if fixture doesn't have it
            if date_start and not item.get("date_start"):
                item = {**item, "date_start": date_start, "date_stop": date_stop}
            yield item

    # ── Dry-run publish (Phase 1 compatibility) ──────────────────

    async def publish_dry_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "dry_run": True,
            "note": "DRY_RUN=true — no write performed.",
            "simulated_ids": {
                "campaign_id": f"mock_campaign_{uuid.uuid4().hex[:8]}",
                "adset_id": f"mock_adset_{uuid.uuid4().hex[:8]}",
                "creative_id": f"mock_creative_{uuid.uuid4().hex[:8]}",
                "ad_id": f"mock_ad_{uuid.uuid4().hex[:8]}",
            },
            "payload_received": payload,
        }
