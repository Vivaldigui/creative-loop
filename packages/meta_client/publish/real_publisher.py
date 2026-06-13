"""
RealPublisher — Phase 6 orchestrator for real Meta Marketing API writes.

Invariants:
  - Every ad is created PAUSED.  The publisher asserts this before and after
    each create_ad call.
  - Non-idempotent operations (create_campaign/adset/creative/ad) never
    auto-retry.  Instead, reconciliation reads back any tag-matching resource
    before retrying.
  - Every step records its x-fb-request-id for audit/debugging.
  - Any step may fail into `failed` or `requires_manual_review`; the attempt
    is resumable from the last completed step.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from packages.meta_client.write_transport import (
    MetaWriteAmbiguousError,
    MetaWriteAuthError,
    MetaWritePermissionError,
    MetaWritePolicyRejectionError,
)

from .dtos import MetaPublishPayload
from .write_client_real import RealMetaWriteClient

logger = structlog.get_logger()

# ── State machine values ─────────────────────────────────────────────────────
WORKFLOW_STATES = [
    "validated",
    "image_uploaded",
    "campaign_resolved",
    "adset_resolved",
    "creative_created",
    "ad_created_paused",
    "status_checked",
    "completed",
]
TERMINAL_STATES = {"completed", "failed", "requires_manual_review"}

# Sanitise keys that might carry secrets before we persist step_payload.
_SENSITIVE_PATTERN = re.compile(r"token|secret|proof|password|key", re.IGNORECASE)


def _sanitize(d: Any) -> Any:
    if isinstance(d, dict):
        return {
            k: "***REDACTED***" if _SENSITIVE_PATTERN.search(k) else _sanitize(v)
            for k, v in d.items()
        }
    if isinstance(d, list):
        return [_sanitize(i) for i in d]
    return d


# ── Step result ──────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    state: str
    meta_node_id: str | None = None
    meta_request_id: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    is_recoverable: bool = True
    step_payload: dict[str, Any] | None = None
    finished_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def success(self) -> bool:
        return self.error_code is None


# ── Main publisher ───────────────────────────────────────────────────────────

@dataclass
class PublishResult:
    """Returned by RealPublisher.publish()."""
    workflow_state: str
    steps: list[StepResult]
    meta_campaign_id: str | None = None
    meta_adset_id: str | None = None
    meta_image_hash: str | None = None
    meta_creative_id: str | None = None
    meta_ad_id: str | None = None
    error_detail: str | None = None
    requires_manual_review: bool = False

    @property
    def succeeded(self) -> bool:
        return self.workflow_state == "completed"


class RealPublisher:
    """
    Executes the 5-step Meta publish sequence for real.

    Steps:
      1. image_uploaded     — upload image bytes → image_hash
      2. campaign_resolved  — create or reconcile campaign
      3. adset_resolved     — create or reconcile adset
      4. creative_created   — create ad creative
      5. ad_created_paused  — create ad (status=PAUSED, asserted)
      6. status_checked     — GET ad back, verify effective_status != ACTIVE
    """

    def __init__(
        self,
        client: RealMetaWriteClient,
        idempotency_tag: str,
    ) -> None:
        """
        idempotency_tag — short unique string injected into resource names
        to enable reconciliation search if a step fails after creation.
        """
        self._client = client
        self._tag = idempotency_tag

    async def publish(
        self,
        payload: MetaPublishPayload,
        *,
        correlation_id: str | None = None,
        resume_from: PartialProgress | None = None,
    ) -> PublishResult:
        """
        Execute the full publish workflow.

        resume_from: if provided, skip already-completed steps and reuse
        their resource IDs (reconciliation path).
        """
        log = logger.bind(correlation_id=correlation_id, tag=self._tag)
        log.info("real_publisher_start")

        account_id = payload.ad_account_id
        steps: list[StepResult] = []

        # Carry-over IDs (from resume or accumulated as we go)
        image_hash: str | None = resume_from.image_hash if resume_from else None
        campaign_id: str | None = resume_from.campaign_id if resume_from else None
        adset_id: str | None = resume_from.adset_id if resume_from else None
        creative_id: str | None = resume_from.creative_id if resume_from else None
        ad_id: str | None = resume_from.ad_id if resume_from else None

        # ── Step 1: Upload image ──────────────────────────────────
        if image_hash is None:
            step = await self._upload_image(account_id, payload)
            steps.append(step)
            if not step.success:
                return self._fail(steps, step, "image_uploaded")
            image_hash = step.meta_node_id

        # ── Step 2: Resolve campaign ──────────────────────────────
        if campaign_id is None:
            step = await self._resolve_campaign(account_id, payload)
            steps.append(step)
            if not step.success:
                return self._fail(steps, step, "campaign_resolved")
            campaign_id = step.meta_node_id

        # ── Step 3: Resolve adset ─────────────────────────────────
        if adset_id is None:
            step = await self._resolve_adset(account_id, payload, campaign_id)
            steps.append(step)
            if not step.success:
                return self._fail(steps, step, "adset_resolved")
            adset_id = step.meta_node_id

        # ── Step 4: Create ad creative ────────────────────────────
        if creative_id is None:
            step = await self._create_creative(account_id, payload, image_hash)
            steps.append(step)
            if not step.success:
                return self._fail(steps, step, "creative_created")
            creative_id = step.meta_node_id

        # ── Step 5: Create ad (PAUSED) ────────────────────────────
        if ad_id is None:
            step = await self._create_ad(account_id, payload, adset_id, creative_id)
            steps.append(step)
            if not step.success:
                return self._fail(steps, step, "ad_created_paused")
            ad_id = step.meta_node_id

        # ── Step 6: Verify PAUSED status ──────────────────────────
        status_step = await self._check_status(ad_id)
        steps.append(status_step)
        if not status_step.success:
            return self._fail(steps, status_step, "status_checked")

        # Effective status must NOT be ACTIVE
        effective = (status_step.step_payload or {}).get("effective_status", "")
        if effective == "ACTIVE":
            logger.error(
                "real_publisher_ad_active_after_create",
                ad_id=ad_id, effective_status=effective, tag=self._tag,
            )
            return PublishResult(
                workflow_state="requires_manual_review",
                steps=steps,
                meta_campaign_id=campaign_id,
                meta_adset_id=adset_id,
                meta_image_hash=image_hash,
                meta_creative_id=creative_id,
                meta_ad_id=ad_id,
                error_detail=(
                    f"Ad {ad_id} has effective_status=ACTIVE after creation — "
                    "this must not happen. Manual review required."
                ),
                requires_manual_review=True,
            )

        log.info(
            "real_publisher_complete",
            ad_id=ad_id,
            campaign_id=campaign_id,
            effective_status=effective,
        )
        return PublishResult(
            workflow_state="completed",
            steps=steps,
            meta_campaign_id=campaign_id,
            meta_adset_id=adset_id,
            meta_image_hash=image_hash,
            meta_creative_id=creative_id,
            meta_ad_id=ad_id,
        )

    # ── Individual steps ──────────────────────────────────────────

    async def _upload_image(
        self, account_id: str, payload: MetaPublishPayload
    ) -> StepResult:

        img = payload.image_upload
        log = logger.bind(filename=img.filename, tag=self._tag)
        log.info("step_upload_image_start")
        try:
            # image_bytes provided via payload.image_upload.raw_bytes (set by service layer)
            raw_bytes: bytes | None = getattr(img, "_raw_bytes", None)
            if not raw_bytes:
                return StepResult(
                    state="image_uploaded",
                    error_code="image_bytes_missing",
                    error_detail="Image bytes were not provided to the publisher.",
                    is_recoverable=False,
                )
            body, req_id = await self._client.upload_image(account_id, raw_bytes, img.filename)
            images = body.get("images", {})
            image_hash = None
            for _name, img_data in images.items():
                image_hash = img_data.get("hash")
                break
            if not image_hash:
                return StepResult(
                    state="image_uploaded",
                    meta_request_id=req_id,
                    error_code="image_hash_missing",
                    error_detail=f"Meta returned no image hash. Response: {json.dumps(_sanitize(body))[:300]}",
                    is_recoverable=True,
                )
            log.info("step_upload_image_done", image_hash=image_hash, request_id=req_id)
            return StepResult(
                state="image_uploaded",
                meta_node_id=image_hash,
                meta_request_id=req_id,
                step_payload=_sanitize({"filename": img.filename, "image_hash": image_hash}),
            )
        except MetaWriteAuthError as exc:
            return StepResult(state="image_uploaded", meta_request_id=exc.request_id,
                              error_code="auth_error", error_detail=str(exc), is_recoverable=False)
        except MetaWritePermissionError as exc:
            return StepResult(state="image_uploaded", meta_request_id=exc.request_id,
                              error_code="permission_error", error_detail=str(exc), is_recoverable=False)
        except Exception as exc:
            return StepResult(state="image_uploaded", error_code="upload_error",
                              error_detail=str(exc), is_recoverable=True)

    async def _resolve_campaign(
        self, account_id: str, payload: MetaPublishPayload
    ) -> StepResult:
        camp = payload.campaign
        tagged_name = f"{camp.name} [{self._tag}]"
        log = logger.bind(name=tagged_name, tag=self._tag)
        log.info("step_resolve_campaign_start")

        # Reconcile: does a campaign with our tag already exist?
        existing = await self._client.find_by_idempotency_tag(account_id, "campaigns", self._tag)
        if existing:
            log.info("step_campaign_reconciled", campaign_id=existing["id"])
            return StepResult(
                state="campaign_resolved",
                meta_node_id=existing["id"],
                step_payload={"reconciled": True, "id": existing["id"], "name": existing.get("name")},
            )

        campaign_payload = {
            "name": tagged_name,
            "objective": camp.objective,
            "status": "PAUSED",
            "special_ad_categories": camp.special_ad_categories,
            "buying_type": camp.buying_type,
        }
        try:
            body, req_id = await self._client.create_campaign(account_id, campaign_payload)
            campaign_id = body.get("id")
            if not campaign_id:
                return StepResult(
                    state="campaign_resolved", meta_request_id=req_id,
                    error_code="no_id_returned",
                    error_detail=f"No 'id' in campaign creation response: {json.dumps(_sanitize(body))[:300]}",
                    is_recoverable=True,
                )
            log.info("step_campaign_created", campaign_id=campaign_id, request_id=req_id)
            return StepResult(
                state="campaign_resolved",
                meta_node_id=campaign_id, meta_request_id=req_id,
                step_payload=_sanitize({"id": campaign_id, "name": tagged_name}),
            )
        except MetaWriteAmbiguousError as exc:
            return StepResult(state="campaign_resolved", meta_request_id=exc.request_id,
                              error_code="ambiguous_error", error_detail=str(exc), is_recoverable=True)
        except (MetaWriteAuthError, MetaWritePermissionError) as exc:
            return StepResult(state="campaign_resolved", meta_request_id=exc.request_id,
                              error_code="auth_or_permission_error", error_detail=str(exc), is_recoverable=False)
        except Exception as exc:
            return StepResult(state="campaign_resolved", error_code="create_error",
                              error_detail=str(exc), is_recoverable=True)

    async def _resolve_adset(
        self, account_id: str, payload: MetaPublishPayload, campaign_id: str
    ) -> StepResult:
        adset = payload.adset
        tagged_name = f"{adset.name} [{self._tag}]"
        log = logger.bind(name=tagged_name, campaign_id=campaign_id, tag=self._tag)
        log.info("step_resolve_adset_start")

        existing = await self._client.find_by_idempotency_tag(account_id, "adsets", self._tag)
        if existing:
            log.info("step_adset_reconciled", adset_id=existing["id"])
            return StepResult(
                state="adset_resolved",
                meta_node_id=existing["id"],
                step_payload={"reconciled": True, "id": existing["id"], "name": existing.get("name")},
            )

        tgt = adset.targeting
        targeting_dict: dict[str, Any] = {
            "geo_locations": {
                "countries": tgt.geo_locations.countries,
                "cities": tgt.geo_locations.cities,
                "regions": tgt.geo_locations.regions,
            },
            "age_min": tgt.age_min,
            "age_max": tgt.age_max,
        }
        if tgt.genders:
            targeting_dict["genders"] = tgt.genders
        if tgt.flexible_spec:
            targeting_dict["flexible_spec"] = tgt.flexible_spec

        adset_payload: dict[str, Any] = {
            "name": tagged_name,
            "campaign_id": campaign_id,
            "daily_budget": adset.daily_budget,
            "billing_event": adset.billing_event,
            "optimization_goal": adset.optimization_goal,
            "bid_strategy": adset.bid_strategy,
            "targeting": json.dumps(targeting_dict),
            "status": "PAUSED",
        }
        if adset.promoted_object:
            promo: dict[str, Any] = {}
            if adset.promoted_object.pixel_id:
                promo["pixel_id"] = adset.promoted_object.pixel_id
            if adset.promoted_object.custom_event_type:
                promo["custom_event_type"] = adset.promoted_object.custom_event_type
            if promo:
                adset_payload["promoted_object"] = json.dumps(promo)
        if adset.start_time:
            adset_payload["start_time"] = adset.start_time

        try:
            body, req_id = await self._client.create_adset(account_id, adset_payload)
            adset_id = body.get("id")
            if not adset_id:
                return StepResult(
                    state="adset_resolved", meta_request_id=req_id,
                    error_code="no_id_returned",
                    error_detail=f"No 'id' in adset creation response: {json.dumps(_sanitize(body))[:300]}",
                    is_recoverable=True,
                )
            log.info("step_adset_created", adset_id=adset_id, request_id=req_id)
            return StepResult(
                state="adset_resolved",
                meta_node_id=adset_id, meta_request_id=req_id,
                step_payload=_sanitize({"id": adset_id, "name": tagged_name}),
            )
        except MetaWriteAmbiguousError as exc:
            return StepResult(state="adset_resolved", meta_request_id=exc.request_id,
                              error_code="ambiguous_error", error_detail=str(exc), is_recoverable=True)
        except (MetaWriteAuthError, MetaWritePermissionError) as exc:
            return StepResult(state="adset_resolved", meta_request_id=exc.request_id,
                              error_code="auth_or_permission_error", error_detail=str(exc), is_recoverable=False)
        except Exception as exc:
            return StepResult(state="adset_resolved", error_code="create_error",
                              error_detail=str(exc), is_recoverable=True)

    async def _create_creative(
        self, account_id: str, payload: MetaPublishPayload, image_hash: str
    ) -> StepResult:
        cr = payload.ad_creative
        tagged_name = f"{cr.name} [{self._tag}]"
        log = logger.bind(name=tagged_name, tag=self._tag)
        log.info("step_create_creative_start")

        existing = await self._client.find_by_idempotency_tag(account_id, "adcreatives", self._tag)
        if existing:
            log.info("step_creative_reconciled", creative_id=existing["id"])
            return StepResult(
                state="creative_created",
                meta_node_id=existing["id"],
                step_payload={"reconciled": True, "id": existing["id"]},
            )

        spec = cr.object_story_spec
        link_data: dict[str, Any] = {"image_hash": image_hash}
        if spec.link_data.link:
            link_data["link"] = spec.link_data.link
        if spec.link_data.message:
            link_data["message"] = spec.link_data.message
        if spec.link_data.name:
            link_data["name"] = spec.link_data.name
        if spec.link_data.description:
            link_data["description"] = spec.link_data.description
        if spec.link_data.call_to_action:
            cta: dict[str, Any] = {"type": spec.link_data.call_to_action.type}
            if spec.link_data.call_to_action.value:
                cta["value"] = json.dumps({"link": spec.link_data.call_to_action.value.link})
            link_data["call_to_action"] = json.dumps(cta)

        story_spec: dict[str, Any] = {
            "page_id": spec.page_id,
            "link_data": json.dumps(link_data),
        }
        if spec.instagram_actor_id:
            story_spec["instagram_actor_id"] = spec.instagram_actor_id

        creative_payload: dict[str, Any] = {
            "name": tagged_name,
            "object_story_spec": json.dumps(story_spec),
        }
        if cr.degrees_of_freedom_spec:
            creative_payload["degrees_of_freedom_spec"] = json.dumps(cr.degrees_of_freedom_spec)

        try:
            body, req_id = await self._client.create_ad_creative(account_id, creative_payload)
            creative_id = body.get("id")
            if not creative_id:
                return StepResult(
                    state="creative_created", meta_request_id=req_id,
                    error_code="no_id_returned",
                    error_detail=f"No 'id' in ad creative response: {json.dumps(_sanitize(body))[:300]}",
                    is_recoverable=True,
                )
            log.info("step_creative_created", creative_id=creative_id, request_id=req_id)
            return StepResult(
                state="creative_created",
                meta_node_id=creative_id, meta_request_id=req_id,
                step_payload=_sanitize({"id": creative_id, "name": tagged_name}),
            )
        except MetaWritePolicyRejectionError as exc:
            return StepResult(state="creative_created", meta_request_id=exc.request_id,
                              error_code="policy_rejection", error_detail=str(exc), is_recoverable=False)
        except MetaWriteAmbiguousError as exc:
            return StepResult(state="creative_created", meta_request_id=exc.request_id,
                              error_code="ambiguous_error", error_detail=str(exc), is_recoverable=True)
        except (MetaWriteAuthError, MetaWritePermissionError) as exc:
            return StepResult(state="creative_created", meta_request_id=exc.request_id,
                              error_code="auth_or_permission_error", error_detail=str(exc), is_recoverable=False)
        except Exception as exc:
            return StepResult(state="creative_created", error_code="create_error",
                              error_detail=str(exc), is_recoverable=True)

    async def _create_ad(
        self,
        account_id: str,
        payload: MetaPublishPayload,
        adset_id: str,
        creative_id: str,
    ) -> StepResult:
        ad = payload.ad
        tagged_name = f"{ad.name} [{self._tag}]"
        log = logger.bind(name=tagged_name, tag=self._tag)
        log.info("step_create_ad_start")

        existing = await self._client.find_by_idempotency_tag(account_id, "ads", self._tag)
        if existing:
            log.info("step_ad_reconciled", ad_id=existing["id"])
            return StepResult(
                state="ad_created_paused",
                meta_node_id=existing["id"],
                step_payload={"reconciled": True, "id": existing["id"]},
            )

        ad_payload: dict[str, Any] = {
            "name": tagged_name,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        }
        if ad.tracking_specs:
            ad_payload["tracking_specs"] = json.dumps(ad.tracking_specs)

        try:
            body, req_id = await self._client.create_ad(account_id, ad_payload)
            ad_id = body.get("id")
            if not ad_id:
                return StepResult(
                    state="ad_created_paused", meta_request_id=req_id,
                    error_code="no_id_returned",
                    error_detail=f"No 'id' in ad creation response: {json.dumps(_sanitize(body))[:300]}",
                    is_recoverable=True,
                )
            log.info("step_ad_created_paused", ad_id=ad_id, request_id=req_id)
            return StepResult(
                state="ad_created_paused",
                meta_node_id=ad_id, meta_request_id=req_id,
                step_payload=_sanitize({"id": ad_id, "name": tagged_name, "status": "PAUSED"}),
            )
        except MetaWritePolicyRejectionError as exc:
            return StepResult(state="ad_created_paused", meta_request_id=exc.request_id,
                              error_code="policy_rejection", error_detail=str(exc), is_recoverable=False)
        except MetaWriteAmbiguousError as exc:
            return StepResult(state="ad_created_paused", meta_request_id=exc.request_id,
                              error_code="ambiguous_error", error_detail=str(exc), is_recoverable=True)
        except (MetaWriteAuthError, MetaWritePermissionError) as exc:
            return StepResult(state="ad_created_paused", meta_request_id=exc.request_id,
                              error_code="auth_or_permission_error", error_detail=str(exc), is_recoverable=False)
        except Exception as exc:
            return StepResult(state="ad_created_paused", error_code="create_error",
                              error_detail=str(exc), is_recoverable=True)

    async def _check_status(self, ad_id: str) -> StepResult:
        log = logger.bind(ad_id=ad_id, tag=self._tag)
        log.info("step_check_status_start")
        try:
            body, req_id = await self._client.get_status(ad_id)
            effective = body.get("effective_status", "")
            configured = body.get("configured_status", body.get("status", ""))
            log.info(
                "step_check_status_done",
                effective=effective, configured=configured, request_id=req_id,
            )
            return StepResult(
                state="status_checked",
                meta_node_id=ad_id, meta_request_id=req_id,
                step_payload={
                    "effective_status": effective,
                    "configured_status": configured,
                },
            )
        except Exception as exc:
            return StepResult(
                state="status_checked",
                error_code="status_check_error",
                error_detail=str(exc),
                is_recoverable=True,
            )

    # ── Helpers ───────────────────────────────────────────────────

    def _fail(
        self,
        steps: list[StepResult],
        failed_step: StepResult,
        at_state: str,
    ) -> PublishResult:
        is_recoverable = failed_step.is_recoverable
        wf_state = "requires_manual_review" if not is_recoverable else "failed"
        logger.warning(
            "real_publisher_step_failed",
            state=at_state,
            error_code=failed_step.error_code,
            error_detail=failed_step.error_detail,
            recoverable=is_recoverable,
            tag=self._tag,
        )
        return PublishResult(
            workflow_state=wf_state,
            steps=steps,
            error_detail=failed_step.error_detail,
            requires_manual_review=not is_recoverable,
        )


# ── Resume context ────────────────────────────────────────────────────────────

@dataclass
class PartialProgress:
    """Carry-over IDs from a previous attempt that completed some steps."""
    image_hash: str | None = None
    campaign_id: str | None = None
    adset_id: str | None = None
    creative_id: str | None = None
    ad_id: str | None = None

    @classmethod
    def from_steps(cls, steps: list[dict[str, Any]]) -> PartialProgress:
        """Reconstruct from serialised PublicationStep dicts."""
        p = cls()
        for s in steps:
            state = s.get("state", "")
            node_id = s.get("meta_node_id")
            if state == "image_uploaded" and node_id:
                p.image_hash = node_id
            elif state == "campaign_resolved" and node_id:
                p.campaign_id = node_id
            elif state == "adset_resolved" and node_id:
                p.adset_id = node_id
            elif state == "creative_created" and node_id:
                p.creative_id = node_id
            elif state == "ad_created_paused" and node_id:
                p.ad_id = node_id
        return p
