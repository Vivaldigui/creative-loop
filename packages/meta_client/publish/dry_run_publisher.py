"""
DryRunPublisher — the ONLY MetaPublisher implementation in Phase 5.

Never calls MetaGraphTransport. Never calls any write method.
Produces a SimulatedPublishResponse with clearly-marked simulated IDs.
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from .dtos import MetaPublishPayload, SimulatedPublishResponse
from .placeholders import is_placeholder
from .serialization import serialize_full_payload

logger = structlog.get_logger()

_STEPS = [
    "1_create_campaign",
    "2_create_adset",
    "3_upload_image",
    "4_create_ad_creative",
    "5_create_ad",
]


def _short_id() -> str:
    return uuid.uuid4().hex[:12]


class DryRunPublisher:
    """
    Simulates a full Meta publish sequence without making any API calls.

    Security guarantee: this class has no reference to MetaGraphTransport,
    RealMetaWriteClient, or httpx. It cannot make network calls.
    """

    async def publish(
        self,
        payload: MetaPublishPayload,
        correlation_id: str | None = None,
    ) -> SimulatedPublishResponse:
        log = logger.bind(
            correlation_id=correlation_id,
            creative_name=payload.campaign.name,
            dry_run=True,
        )
        log.info("dry_run_publisher_start")

        # Collect placeholders present in the payload
        placeholders: list[str] = []
        _scan_placeholders(payload, placeholders)

        simulated = SimulatedPublishResponse(
            simulated_campaign_id=f"simulated_campaign_{_short_id()}",
            simulated_adset_id=f"simulated_adset_{_short_id()}",
            simulated_image_hash=f"simulated_imghash_{_short_id()}",
            simulated_ad_creative_id=f"simulated_creative_{_short_id()}",
            simulated_ad_id=f"simulated_ad_{_short_id()}",
            steps_simulated=_STEPS,
            placeholders_present=placeholders,
        )

        log.info(
            "dry_run_publisher_complete",
            simulated_ad_id=simulated.simulated_ad_id,
            placeholders_count=len(placeholders),
        )
        return simulated

    async def serialize_payload(self, payload: MetaPublishPayload) -> dict[str, Any]:
        """Return the full serialised dict (for preview/storage)."""
        return serialize_full_payload(payload)


def _scan_placeholders(payload: MetaPublishPayload, out: list[str]) -> None:
    """Walk the payload and collect any placeholder values for reporting."""
    checks = {
        "ad_account_id": payload.ad_account_id,
        "page_id": payload.page_id,
        "instagram_actor_id": payload.instagram_actor_id,
        "pixel_id": payload.pixel_id,
        "adcreative_page_id": payload.ad_creative.object_story_spec.page_id,
        "adcreative_instagram_actor_id": payload.ad_creative.object_story_spec.instagram_actor_id,
        "adcreative_image_hash": payload.ad_creative.object_story_spec.link_data.image_hash,
    }
    for field, value in checks.items():
        if is_placeholder(value):
            out.append(field)
