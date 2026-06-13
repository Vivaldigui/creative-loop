"""
PublicationService — orchestrates both DRY_RUN simulation and real Meta publish.

DRY_RUN path:  dry_run()
Real path:     publish_real()
Activation:    activate(), pause(), emergency_pause()
Status:        refresh_status()
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from packages.meta_client.publish.dtos import (
    AdCreativePayload,
    AdPayload,
    AdSetPayload,
    CallToAction,
    CampaignPayload,
    CtaValue,
    ImageUploadPayload,
    LinkData,
    MetaPublishPayload,
    ObjectStorySpec,
    PromotedObject,
    Targeting,
)
from packages.meta_client.publish.factory import get_meta_publisher
from packages.meta_client.publish.placeholders import (
    PENDING_META_AD_ACCOUNT_ID,
    PENDING_META_IMAGE_HASH,
    PENDING_META_INSTAGRAM_ACTOR_ID,
    PENDING_META_PAGE_ID,
    PENDING_META_PIXEL_ID,
    is_placeholder,
    resolve,
)
from packages.meta_client.publish.serialization import serialize_full_payload
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.approval import Approval
from app.models.audit import AuditLog
from app.models.checks import CHECK_RESULT_BLOCKED, PolicyCheck, QualityCheck
from app.models.creative import GeneratedCreative
from app.models.publication import PublicationAttempt, PublicationDraft
from app.models.publish import PublicationStep, PublishedAd
from app.models.user import User

from .publication_guards import (
    GuardContext,
    has_blocking_failure,
    is_safe_retry,
    results_to_dict,
    run_all_guards,
)

logger = structlog.get_logger()


def _canonical_hash(payload_dict: dict[str, Any]) -> str:
    """Deterministic sha256 over JSON with sorted keys, excluding volatile fields."""
    # Drop fields that change between calls but not payload identity
    clean = {k: v for k, v in payload_dict.items() if k not in ("correlation_id", "created_at", "updated_at")}
    raw = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _sanitize_payload(payload_dict: dict[str, Any]) -> dict[str, Any]:
    """Strip any field that might contain a secret token before storing in AuditLog."""
    sensitive = {"access_token", "appsecret_proof", "secret", "token", "key", "password"}
    if not isinstance(payload_dict, dict):
        return payload_dict

    return {
        k: "***REDACTED***" if any(s in k.lower() for s in sensitive) else (
            _sanitize_payload(v) if isinstance(v, dict) else v
        )
        for k, v in payload_dict.items()
    }


class PublicationService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── Payload builder ───────────────────────────────────────────

    def build_payload(
        self,
        *,
        creative: GeneratedCreative,
        campaign_name: str,
        adset_name: str,
        ad_name: str,
        objective: str = "OUTCOME_TRAFFIC",
        optimization_goal: str = "LINK_CLICKS",
        billing_event: str = "IMPRESSIONS",
        bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
        daily_budget_brl: float,
        landing_url: str | None = None,
        tracking_params: dict[str, str] | None = None,
        headline: str | None = None,
        body_text: str | None = None,
        cta_type: str = "SHOP_NOW",
        targeting: dict[str, Any] | None = None,
        placements: list[str] | None = None,
        promoted_object: dict[str, Any] | None = None,
        degrees_of_freedom_spec: dict[str, Any] | None = None,
    ) -> MetaPublishPayload:
        s = self._settings

        # Resolve placeholders from settings
        account_id = resolve(s.meta_ad_account_id, PENDING_META_AD_ACCOUNT_ID)
        page_id = resolve(s.meta_page_id, PENDING_META_PAGE_ID)
        instagram_actor_id = resolve(s.meta_instagram_actor_id, PENDING_META_INSTAGRAM_ACTOR_ID)
        pixel_id = resolve(s.meta_pixel_id, PENDING_META_PIXEL_ID)

        # daily_budget in centavos (BRL smallest unit)
        daily_budget_centavos = int(daily_budget_brl * 100)

        # Targeting
        tgt = Targeting()
        if targeting:
            tgt = Targeting.model_validate(targeting)

        # Promoted object
        promo_obj = None
        if promoted_object:
            promo_obj = PromotedObject.model_validate(promoted_object)
        elif not is_placeholder(pixel_id):
            promo_obj = PromotedObject(pixel_id=pixel_id, custom_event_type="PURCHASE")

        # Image: use storage_key from creative or fall back to file_path
        storage_key = creative.storage_key or creative.file_path or ""
        image_hash = creative.file_hash or ""

        campaign = CampaignPayload(name=campaign_name, objective=objective)
        adset = AdSetPayload(
            name=adset_name,
            campaign_id="simulated_campaign_placeholder",
            daily_budget=daily_budget_centavos,
            optimization_goal=optimization_goal,
            billing_event=billing_event,
            bid_strategy=bid_strategy,
            targeting=tgt,
            promoted_object=promo_obj,
        )
        image_upload = ImageUploadPayload(
            source_storage_key=storage_key,
            image_hash=image_hash,
            bytes_len=creative.file_size_bytes or 0,
            filename=f"creative_{creative.id}.png",
            placeholder_image_hash=PENDING_META_IMAGE_HASH,
        )

        cta = None
        if landing_url:
            cta = CallToAction(type=cta_type, value=CtaValue(link=landing_url))

        link_data = LinkData(
            image_hash=PENDING_META_IMAGE_HASH,
            message=body_text,
            name=headline,
            call_to_action=cta,
            link=landing_url,
        )

        story_spec = ObjectStorySpec(
            page_id=page_id,
            instagram_actor_id=instagram_actor_id if not is_placeholder(instagram_actor_id) else None,
            link_data=link_data,
        )
        ad_creative = AdCreativePayload(
            name=f"{ad_name} creative",
            object_story_spec=story_spec,
            degrees_of_freedom_spec=degrees_of_freedom_spec,
        )
        ad = AdPayload(
            name=ad_name,
            adset_id="simulated_adset_placeholder",
            creative={"creative_id": "simulated_ad_creative_placeholder"},
        )

        return MetaPublishPayload(
            graph_api_version=s.meta_graph_api_version,
            ad_account_id=account_id,
            page_id=page_id,
            instagram_actor_id=instagram_actor_id if not is_placeholder(instagram_actor_id) else None,
            pixel_id=pixel_id if not is_placeholder(pixel_id) else None,
            placements=placements or ["facebook_feed", "instagram_feed"],
            url=landing_url,
            tracking_params=tracking_params or {},
            campaign=campaign,
            adset=adset,
            image_upload=image_upload,
            ad_creative=ad_creative,
            ad=ad,
        )

    # ── Guard context builder ─────────────────────────────────────

    async def _build_guard_context(
        self,
        *,
        db: AsyncSession,
        creative: GeneratedCreative,
        actor: User,
        org_id: uuid.UUID,
        daily_budget_brl: float | None,
        landing_url: str | None,
        objective: str | None,
        optimization_goal: str | None,
        idempotency_key: str,
        current_payload_hash: str,
        experiment_id: uuid.UUID | None,
    ) -> GuardContext:
        s = self._settings

        # Approval
        approval_row = (await db.execute(
            select(Approval).where(
                Approval.creative_id == creative.id,
                Approval.decision == "approved",
            ).limit(1)
        )).scalar_one_or_none()

        # Blocked checks
        blocked_quality = (await db.execute(
            select(QualityCheck).where(
                QualityCheck.creative_id == creative.id,
                QualityCheck.result == CHECK_RESULT_BLOCKED,
                QualityCheck.override_by.is_(None),
            ).limit(1)
        )).scalar_one_or_none()

        blocked_policy = (await db.execute(
            select(PolicyCheck).where(
                PolicyCheck.creative_id == creative.id,
                PolicyCheck.result == CHECK_RESULT_BLOCKED,
                PolicyCheck.override_by.is_(None),
            ).limit(1)
        )).scalar_one_or_none()

        # Idempotency lookup (within TTL window)
        ttl_cutoff = datetime.now(UTC) - timedelta(hours=s.publication_idempotency_ttl_hours)
        prev_attempt = (await db.execute(
            select(PublicationAttempt).where(
                PublicationAttempt.organization_id == org_id,
                PublicationAttempt.idempotency_key == idempotency_key,
                PublicationAttempt.created_at >= ttl_cutoff,
            ).limit(1)
        )).scalar_one_or_none()

        # Daily simulations count
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = (await db.execute(
            select(func.count(PublicationAttempt.id)).where(
                PublicationAttempt.organization_id == org_id,
                PublicationAttempt.result == "simulated",
                PublicationAttempt.created_at >= today_start,
            )
        )).scalar_one()

        # Experiment budget used
        exp_budget_used = 0.0
        if experiment_id and s.max_experiment_budget:
            # Sum of daily_budget from adset configs in simulated attempts for this experiment
            draft_ids_result = await db.execute(
                select(PublicationDraft.id).where(
                    PublicationDraft.experiment_id == experiment_id,
                    PublicationDraft.organization_id == org_id,
                )
            )
            draft_ids = [r[0] for r in draft_ids_result.fetchall()]
            if draft_ids:
                for did in draft_ids:
                    att = (await db.execute(
                        select(PublicationAttempt).where(
                            PublicationAttempt.draft_id == did,
                            PublicationAttempt.result == "simulated",
                        ).limit(1)
                    )).scalar_one_or_none()
                    if att and att.payload:
                        budget_centavos = (
                            att.payload.get("steps", {})
                            .get("2_adset", {})
                            .get("daily_budget", 0)
                        )
                        exp_budget_used += budget_centavos / 100.0

        page_id = s.meta_page_id
        has_page = not is_placeholder(page_id)

        return GuardContext(
            actor_role=actor.role,
            org_id=org_id,
            creative_org_id=creative.organization_id,
            creative_status=creative.status,
            creative_id=creative.id,
            has_approval=approval_row is not None,
            approval_id=approval_row.id if approval_row else None,
            has_blocked_quality_check=blocked_quality is not None,
            has_blocked_policy_check=blocked_policy is not None,
            daily_budget_brl=daily_budget_brl,
            max_daily_spend=s.max_daily_spend,
            max_experiment_budget=s.max_experiment_budget,
            experiment_id=experiment_id,
            experiment_budget_used=exp_budget_used,
            daily_simulated_count=int(daily_count),
            max_daily_new_ads=s.max_daily_new_ads,
            landing_url=landing_url,
            objective=objective,
            optimization_goal=optimization_goal,
            has_page_reference=has_page,
            idempotency_key=idempotency_key,
            previous_attempt_id=prev_attempt.id if prev_attempt else None,
            previous_payload_hash=prev_attempt.payload_hash if prev_attempt else None,
            current_payload_hash=current_payload_hash,
            idempotency_ttl_hours=s.publication_idempotency_ttl_hours,
            require_human_approval=s.require_human_approval,
            dry_run=s.dry_run,
            meta_write_enabled=s.meta_write_enabled,
            credentials_valid=False,   # default; override in real-mode context builder
            audit_available=True,
            extra={
                "max_daily_spend": s.max_daily_spend,
                "max_experiment_budget": s.max_experiment_budget,
                "max_daily_new_ads": s.max_daily_new_ads,
                "daily_count_today": daily_count,
            },
        )

    # ── Validate (no persistence) ─────────────────────────────────

    async def validate(
        self,
        *,
        db: AsyncSession,
        creative: GeneratedCreative,
        actor: User,
        org_id: uuid.UUID,
        payload: MetaPublishPayload,
        daily_budget_brl: float | None,
        landing_url: str | None,
        objective: str | None,
        optimization_goal: str | None,
        idempotency_key: str,
        experiment_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Run all guards and return structured results. Does NOT persist anything."""
        payload_dict = serialize_full_payload(payload)
        payload_hash = _canonical_hash(payload_dict)

        ctx = await self._build_guard_context(
            db=db,
            creative=creative,
            actor=actor,
            org_id=org_id,
            daily_budget_brl=daily_budget_brl,
            landing_url=landing_url,
            objective=objective,
            optimization_goal=optimization_goal,
            idempotency_key=idempotency_key,
            current_payload_hash=payload_hash,
            experiment_id=experiment_id,
        )
        results = run_all_guards(ctx)
        return results_to_dict(results)

    # ── DRY_RUN simulate ──────────────────────────────────────────

    async def dry_run(
        self,
        *,
        db: AsyncSession,
        creative: GeneratedCreative,
        actor: User,
        org_id: uuid.UUID,
        payload: MetaPublishPayload,
        daily_budget_brl: float | None,
        landing_url: str | None,
        objective: str | None,
        optimization_goal: str | None,
        idempotency_key: str,
        correlation_id: str,
        experiment_id: uuid.UUID | None = None,
        draft_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Full DRY_RUN simulation flow:
        1. Build payload dict + hash
        2. Build guard context
        3. Run guards
        4. Resolve idempotency (return early if safe retry)
        5. Write intent AuditLog
        6. Call DryRunPublisher
        7. Persist PublicationAttempt + PublishedAd
        8. Write result AuditLog
        """
        payload_dict = serialize_full_payload(payload)
        payload_hash = _canonical_hash(payload_dict)

        ctx = await self._build_guard_context(
            db=db,
            creative=creative,
            actor=actor,
            org_id=org_id,
            daily_budget_brl=daily_budget_brl,
            landing_url=landing_url,
            objective=objective,
            optimization_goal=optimization_goal,
            idempotency_key=idempotency_key,
            current_payload_hash=payload_hash,
            experiment_id=experiment_id,
        )

        results = run_all_guards(ctx)
        results_list = results_to_dict(results)

        # ── Safe retry: return previous attempt ──────────────────
        if is_safe_retry(results):
            prev = (await db.execute(
                select(PublicationAttempt).where(
                    PublicationAttempt.organization_id == org_id,
                    PublicationAttempt.idempotency_key == idempotency_key,
                ).limit(1)
            )).scalar_one()
            logger.info(
                "publication_dry_run_idempotent_retry",
                attempt_id=str(prev.id),
                correlation_id=correlation_id,
            )
            return {
                "attempt_id": str(prev.id),
                "published_ad_id": str(prev.published_ad_id) if prev.published_ad_id else None,
                "dry_run": True,
                "mode": "DRY_RUN",
                "idempotent": True,
                "result": prev.result,
                "checks": prev.checks,
                "simulated_response": prev.simulated_response,
                "payload": prev.payload,
                "correlation_id": correlation_id,
                "message": "Idempotent retry — returning existing simulation result.",
            }

        # ── Blocking failure ──────────────────────────────────────
        if has_blocking_failure(results):
            blocked = [r for r in results_list if not r["passed"] and r["severity"] == "blocked"]
            blocked_codes = {b["code"] for b in blocked}

            # Record rejection in AuditLog
            audit = AuditLog(
                organization_id=org_id,
                actor_id=actor.id,
                action="publish_dry_run_rejected",
                entity_type="generated_creative",
                entity_id=str(creative.id),
                payload=_sanitize_payload(payload_dict),
                result="rejected",
                dry_run=True,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                approval_id=ctx.approval_id,
                limits_checked=ctx.extra,
                error_detail="; ".join(b["detail"] for b in blocked),
            )
            db.add(audit)

            # For idempotency conflicts, a PublicationAttempt already exists — skip INSERT
            if "idempotency_conflict" in blocked_codes:
                prev = (await db.execute(
                    select(PublicationAttempt).where(
                        PublicationAttempt.organization_id == org_id,
                        PublicationAttempt.idempotency_key == idempotency_key,
                    ).limit(1)
                )).scalar_one()
                await db.commit()
                return {
                    "attempt_id": str(prev.id),
                    "dry_run": True,
                    "result": "rejected",
                    "checks": results_list,
                    "message": "Idempotency conflict — same key submitted with different payload.",
                    "blocked": blocked,
                    "correlation_id": correlation_id,
                }

            attempt = PublicationAttempt(
                organization_id=org_id,
                draft_id=draft_id,
                creative_id=creative.id,
                idempotency_key=idempotency_key,
                payload=payload_dict,
                payload_hash=payload_hash,
                correlation_id=correlation_id,
                checks=results_list,
                result="rejected",
                error_detail="; ".join(b["detail"] for b in blocked),
            )
            db.add(attempt)
            await db.commit()

            return {
                "attempt_id": str(attempt.id),
                "dry_run": True,
                "result": "rejected",
                "checks": results_list,
                "message": "Simulation rejected by guard checks.",
                "blocked": blocked,
                "correlation_id": correlation_id,
            }

        # ── Intent AuditLog ───────────────────────────────────────
        audit_intent = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="publish_dry_run_intent",
            entity_type="generated_creative",
            entity_id=str(creative.id),
            payload=_sanitize_payload(payload_dict),
            result="dry_run",
            dry_run=True,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            approval_id=ctx.approval_id,
            limits_checked=ctx.extra,
        )
        db.add(audit_intent)
        await db.flush()

        # ── Simulate via DryRunPublisher ──────────────────────────
        publisher = get_meta_publisher(dry_run=True)
        simulated = await publisher.publish(payload, correlation_id=correlation_id)
        simulated_dict = simulated.model_dump()

        # ── Persist PublishedAd ───────────────────────────────────
        published = PublishedAd(
            organization_id=org_id,
            creative_id=creative.id,
            idempotency_key=idempotency_key,
            dry_run=True,
            payload=payload_dict,
            status="dry_run",
        )
        db.add(published)
        await db.flush()

        # ── Persist PublicationAttempt ────────────────────────────
        attempt = PublicationAttempt(
            organization_id=org_id,
            draft_id=draft_id,
            creative_id=creative.id,
            idempotency_key=idempotency_key,
            payload=payload_dict,
            payload_hash=payload_hash,
            correlation_id=correlation_id,
            checks=results_list,
            simulated_response=simulated_dict,
            result="simulated",
            published_ad_id=published.id,
        )
        db.add(attempt)
        await db.flush()

        # Update draft status if provided
        if draft_id:
            draft = (await db.execute(
                select(PublicationDraft).where(
                    PublicationDraft.id == draft_id,
                    PublicationDraft.organization_id == org_id,
                )
            )).scalar_one_or_none()
            if draft:
                draft.status = "simulated"
                draft.payload = payload_dict
                draft.payload_hash = payload_hash

        # ── Result AuditLog ───────────────────────────────────────
        audit_result = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="publish_dry_run_result",
            entity_type="publication_attempt",
            entity_id=str(attempt.id),
            payload={
                "simulated_ad_id": simulated.simulated_ad_id,
                "placeholders_present": simulated.placeholders_present,
            },
            result="dry_run",
            dry_run=True,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            approval_id=ctx.approval_id,
            limits_checked=ctx.extra,
        )
        db.add(audit_result)
        await db.commit()
        await db.refresh(attempt)

        logger.info(
            "publication_dry_run_complete",
            attempt_id=str(attempt.id),
            simulated_ad_id=simulated.simulated_ad_id,
            correlation_id=correlation_id,
            placeholders=simulated.placeholders_present,
        )

        return {
            "attempt_id": str(attempt.id),
            "published_ad_id": str(published.id),
            "dry_run": True,
            "mode": "DRY_RUN",
            "idempotent": False,
            "result": "simulated",
            "checks": results_list,
            "simulated_response": simulated_dict,
            "payload": payload_dict,
            "correlation_id": correlation_id,
            "message": "DRY_RUN simulation complete. No real Meta API call was made.",
        }

    # ═══════════════════════════════════════════════════════════════
    # REAL PUBLISH (Phase 6)
    # ═══════════════════════════════════════════════════════════════

    async def publish_real(
        self,
        *,
        db: AsyncSession,
        creative: GeneratedCreative,
        actor: User,
        org_id: uuid.UUID,
        payload: MetaPublishPayload,
        image_bytes: bytes,
        daily_budget_brl: float,
        landing_url: str,
        objective: str,
        optimization_goal: str,
        idempotency_key: str,
        correlation_id: str,
        credentials_valid: bool,
        experiment_id: uuid.UUID | None = None,
        draft_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Execute real Meta publish:
        1. Run real-mode gate (11 guards)
        2. Audit intent
        3. Persist PublishedAd + PublicationAttempt (initial)
        4. Execute RealPublisher step-by-step
        5. Persist PublicationStep records
        6. Update PublishedAd / PublicationAttempt with final state
        7. Audit result
        """
        from packages.meta_client.publish.real_publisher import PublishResult

        s = self._settings
        payload_dict = serialize_full_payload(payload)
        payload_hash = _canonical_hash(payload_dict)
        idempotency_tag = idempotency_key[:16]

        # Inject raw_bytes — bypass Pydantic's field validation for this internal attribute
        object.__setattr__(payload.image_upload, "_raw_bytes", image_bytes)

        ctx = await self._build_guard_context(
            db=db,
            creative=creative,
            actor=actor,
            org_id=org_id,
            daily_budget_brl=daily_budget_brl,
            landing_url=landing_url,
            objective=objective,
            optimization_goal=optimization_goal,
            idempotency_key=idempotency_key,
            current_payload_hash=payload_hash,
            experiment_id=experiment_id,
        )
        # Override Phase-6-specific fields
        ctx.credentials_valid = credentials_valid
        ctx.meta_write_enabled = s.meta_write_enabled
        ctx.dry_run = False  # we're in real mode

        results = run_all_guards(ctx, mode="real")
        results_list = results_to_dict(results)

        # ── Idempotent safe retry ─────────────────────────────────
        if is_safe_retry(results):
            prev = (await db.execute(
                select(PublicationAttempt).where(
                    PublicationAttempt.organization_id == org_id,
                    PublicationAttempt.idempotency_key == idempotency_key,
                ).limit(1)
            )).scalar_one()
            return {
                "attempt_id": str(prev.id),
                "published_ad_id": str(prev.published_ad_id) if prev.published_ad_id else None,
                "mode": "REAL",
                "idempotent": True,
                "result": prev.result,
                "checks": prev.checks,
                "workflow_state": None,
                "correlation_id": correlation_id,
                "message": "Idempotent retry — returning existing publish result.",
            }

        # ── Gate failure ──────────────────────────────────────────
        if has_blocking_failure(results):
            blocked = [r for r in results_list if not r["passed"] and r["severity"] == "blocked"]
            audit = AuditLog(
                organization_id=org_id,
                actor_id=actor.id,
                action="publish_real_rejected",
                entity_type="generated_creative",
                entity_id=str(creative.id),
                payload=_sanitize_payload(payload_dict),
                result="rejected",
                dry_run=False,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                approval_id=ctx.approval_id,
                limits_checked=ctx.extra,
                error_detail="; ".join(r["detail"] for r in blocked),
            )
            db.add(audit)
            attempt = PublicationAttempt(
                organization_id=org_id,
                draft_id=draft_id,
                creative_id=creative.id,
                idempotency_key=idempotency_key,
                payload=payload_dict,
                payload_hash=payload_hash,
                mode="REAL",
                correlation_id=correlation_id,
                checks=results_list,
                result="rejected",
                error_detail="; ".join(r["detail"] for r in blocked),
            )
            db.add(attempt)
            await db.commit()
            return {
                "attempt_id": str(attempt.id),
                "mode": "REAL",
                "result": "rejected",
                "checks": results_list,
                "blocked": blocked,
                "message": "Real publish rejected by guard checks.",
                "correlation_id": correlation_id,
            }

        # ── Intent AuditLog ───────────────────────────────────────
        audit_intent = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="publish_real_intent",
            entity_type="generated_creative",
            entity_id=str(creative.id),
            payload=_sanitize_payload(payload_dict),
            result="in_progress",
            dry_run=False,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            approval_id=ctx.approval_id,
            limits_checked=ctx.extra,
        )
        db.add(audit_intent)

        # ── Create PublishedAd and Attempt (initial state) ────────
        published = PublishedAd(
            organization_id=org_id,
            creative_id=creative.id,
            idempotency_key=idempotency_key,
            dry_run=False,
            payload=payload_dict,
            status="PAUSED",
            workflow_state="validated",
            idempotency_tag=idempotency_tag,
        )
        db.add(published)
        await db.flush()

        attempt = PublicationAttempt(
            organization_id=org_id,
            draft_id=draft_id,
            creative_id=creative.id,
            idempotency_key=idempotency_key,
            payload=payload_dict,
            payload_hash=payload_hash,
            mode="REAL",
            correlation_id=correlation_id,
            checks=results_list,
            result="in_progress",
            published_ad_id=published.id,
        )
        db.add(attempt)
        await db.flush()
        await db.commit()

        # ── Execute real publish ───────────────────────────────────
        publisher = get_meta_publisher(
            dry_run=False,
            write_enabled=s.meta_write_enabled,
            access_token=s.meta_access_token,
            app_secret=s.meta_app_secret,
            api_version=s.meta_graph_api_version,
            max_retries=s.meta_write_max_retries,
            timeout_s=s.meta_write_timeout_s,
            idempotency_tag=idempotency_tag,
        )

        pub_result: PublishResult = await publisher.publish(
            payload, correlation_id=correlation_id
        )

        # ── Persist PublicationStep records ───────────────────────
        meta_request_ids: dict[str, str] = {}
        for step in pub_result.steps:
            ps = PublicationStep(
                organization_id=org_id,
                attempt_id=attempt.id,
                state=step.state,
                meta_node_id=step.meta_node_id,
                meta_request_id=step.meta_request_id,
                error_code=step.error_code,
                error_detail=step.error_detail,
                is_recoverable=step.is_recoverable,
                step_payload=step.step_payload,
                finished_at=step.finished_at,
            )
            db.add(ps)
            if step.meta_request_id:
                meta_request_ids[step.state] = step.meta_request_id

        # ── Update PublishedAd ─────────────────────────────────────
        final_result = "published" if pub_result.succeeded else pub_result.workflow_state
        published.meta_campaign_id = pub_result.meta_campaign_id
        published.meta_adset_id = pub_result.meta_adset_id
        published.meta_image_hash = pub_result.meta_image_hash
        published.meta_creative_id = pub_result.meta_creative_id
        published.meta_ad_id = pub_result.meta_ad_id
        published.workflow_state = pub_result.workflow_state
        published.status = "PAUSED" if pub_result.succeeded else pub_result.workflow_state
        published.error_detail = pub_result.error_detail

        # ── Update PublicationAttempt ─────────────────────────────
        attempt.result = final_result
        attempt.meta_request_ids = meta_request_ids
        if pub_result.error_detail:
            attempt.error_detail = pub_result.error_detail

        # ── Result AuditLog ───────────────────────────────────────
        audit_result = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="publish_real_result",
            entity_type="publication_attempt",
            entity_id=str(attempt.id),
            payload={
                "workflow_state": pub_result.workflow_state,
                "meta_ad_id": pub_result.meta_ad_id,
                "meta_campaign_id": pub_result.meta_campaign_id,
                "steps_count": len(pub_result.steps),
            },
            result="success" if pub_result.succeeded else "error",
            dry_run=False,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            approval_id=ctx.approval_id,
            limits_checked=ctx.extra,
            error_detail=pub_result.error_detail,
        )
        db.add(audit_result)
        await db.commit()
        await db.refresh(attempt)

        logger.info(
            "publish_real_complete",
            attempt_id=str(attempt.id),
            workflow_state=pub_result.workflow_state,
            meta_ad_id=pub_result.meta_ad_id,
            correlation_id=correlation_id,
        )

        return {
            "attempt_id": str(attempt.id),
            "published_ad_id": str(published.id),
            "mode": "REAL",
            "idempotent": False,
            "result": final_result,
            "workflow_state": pub_result.workflow_state,
            "meta_ad_id": pub_result.meta_ad_id,
            "meta_campaign_id": pub_result.meta_campaign_id,
            "meta_adset_id": pub_result.meta_adset_id,
            "meta_creative_id": pub_result.meta_creative_id,
            "meta_image_hash": pub_result.meta_image_hash,
            "checks": results_list,
            "error_detail": pub_result.error_detail,
            "requires_manual_review": pub_result.requires_manual_review,
            "correlation_id": correlation_id,
            "message": (
                "Ad created PAUSED. Activate manually via POST /published-ads/{id}/activate."
                if pub_result.succeeded
                else f"Publish {pub_result.workflow_state}: {pub_result.error_detail}"
            ),
        }

    # ─────────────────────────────────────────────────────────────
    # STATUS REFRESH
    # ─────────────────────────────────────────────────────────────

    async def refresh_status(
        self,
        *,
        db: AsyncSession,
        published_ad: PublishedAd,
        actor: User,
        org_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Query Meta for current effective_status and persist it."""
        s = self._settings
        if not published_ad.meta_ad_id:
            return {"error": "No meta_ad_id to query.", "published_ad_id": str(published_ad.id)}

        from packages.meta_client.publish.write_client_real import RealMetaWriteClient

        client = RealMetaWriteClient(
            access_token=s.meta_access_token,
            app_secret=s.meta_app_secret,
            api_version=s.meta_graph_api_version,
            max_retries=s.meta_write_max_retries,
            timeout_s=s.meta_write_timeout_s,
        )
        try:
            body, req_id = await client.get_status(published_ad.meta_ad_id)
        except Exception as exc:
            return {"error": str(exc), "published_ad_id": str(published_ad.id)}

        effective = body.get("effective_status", "")
        configured = body.get("configured_status", body.get("status", ""))
        now = datetime.now(UTC)
        published_ad.effective_status = effective
        published_ad.last_status_checked_at = now

        # If Meta returned ACTIVE unexpectedly, flag for manual review
        if effective == "ACTIVE" and published_ad.status != "ACTIVE":
            published_ad.workflow_state = "requires_manual_review"
            logger.error(
                "unexpected_active_status",
                published_ad_id=str(published_ad.id),
                meta_ad_id=published_ad.meta_ad_id,
            )

        db.add(AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="refresh_status",
            entity_type="published_ad",
            entity_id=str(published_ad.id),
            payload={"effective_status": effective, "configured_status": configured,
                     "request_id": req_id},
            result="success",
            dry_run=False,
        ))
        await db.commit()
        return {
            "published_ad_id": str(published_ad.id),
            "meta_ad_id": published_ad.meta_ad_id,
            "effective_status": effective,
            "configured_status": configured,
            "checked_at": now.isoformat(),
        }

    # ─────────────────────────────────────────────────────────────
    # MANUAL ACTIVATION
    # ─────────────────────────────────────────────────────────────

    async def activate(
        self,
        *,
        db: AsyncSession,
        published_ad: PublishedAd,
        actor: User,
        org_id: uuid.UUID,
        confirmation: str,
    ) -> dict[str, Any]:
        """
        Manually activate a PAUSED ad.
        Requires elevated role (owner), explicit confirmation, and re-validates limits.
        Blocked if ad is rejected/disapproved.
        """
        s = self._settings

        # Role check
        if s.meta_require_elevated_for_activation and actor.role != "owner":
            return {
                "error": f"Activation requires role 'owner'; current role is '{actor.role}'.",
                "blocked": True,
            }

        # Confirmation check
        if s.meta_activation_require_confirmation:
            expected = published_ad.meta_ad_id or str(published_ad.id)
            if confirmation != expected:
                return {
                    "error": (
                        f"Confirmation mismatch. Provide confirmation='{expected}' "
                        "to confirm activation."
                    ),
                    "blocked": True,
                }

        # Must have a real meta_ad_id
        if not published_ad.meta_ad_id:
            return {"error": "No meta_ad_id — ad was never successfully created.", "blocked": True}

        # Block if rejected
        if published_ad.rejection_reason or published_ad.effective_status in (
            "DISAPPROVED", "WITH_ISSUES", "PREAPPROVED"
        ):
            return {
                "error": (
                    f"Ad cannot be activated: status is '{published_ad.effective_status}' "
                    f"/ rejection: {published_ad.rejection_reason}."
                ),
                "blocked": True,
            }

        # Block if workflow not completed
        if published_ad.workflow_state not in ("completed", "PAUSED"):
            return {
                "error": (
                    f"Ad workflow_state is '{published_ad.workflow_state}' — "
                    "only fully published (completed) ads can be activated."
                ),
                "blocked": True,
            }

        # Re-verify limits at activation time
        if s.max_daily_spend is not None:
            budget_brl = (published_ad.payload or {}).get("steps", {}).get(
                "2_adset", {}
            ).get("daily_budget", 0) / 100.0
            if budget_brl > s.max_daily_spend:
                return {
                    "error": (
                        f"Budget {budget_brl:.2f} exceeds MAX_DAILY_SPEND "
                        f"{s.max_daily_spend:.2f} at activation time."
                    ),
                    "blocked": True,
                }

        from packages.meta_client.publish.write_client_real import RealMetaWriteClient

        client = RealMetaWriteClient(
            access_token=s.meta_access_token,
            app_secret=s.meta_app_secret,
            api_version=s.meta_graph_api_version,
            max_retries=1,   # activation is non-idempotent: single attempt
            timeout_s=s.meta_write_timeout_s,
        )

        # Intent audit
        db.add(AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="activate_intent",
            entity_type="published_ad",
            entity_id=str(published_ad.id),
            payload={"meta_ad_id": published_ad.meta_ad_id},
            result="in_progress",
            dry_run=False,
        ))
        await db.flush()

        try:
            body, req_id = await client.update_ad_status(published_ad.meta_ad_id, "ACTIVE")
        except Exception as exc:
            db.add(AuditLog(
                organization_id=org_id,
                actor_id=actor.id,
                action="activate_result",
                entity_type="published_ad",
                entity_id=str(published_ad.id),
                payload={"meta_ad_id": published_ad.meta_ad_id, "error": str(exc)},
                result="error",
                dry_run=False,
                error_detail=str(exc),
            ))
            await db.commit()
            return {"error": str(exc), "blocked": False, "meta_ad_id": published_ad.meta_ad_id}

        now = datetime.now(UTC)
        published_ad.status = "ACTIVE"
        published_ad.effective_status = "ACTIVE"
        published_ad.activated_at = now
        published_ad.activated_by = actor.id

        db.add(AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action="activate_result",
            entity_type="published_ad",
            entity_id=str(published_ad.id),
            payload={"meta_ad_id": published_ad.meta_ad_id, "request_id": req_id},
            result="success",
            dry_run=False,
        ))
        await db.commit()

        logger.info(
            "ad_activated",
            published_ad_id=str(published_ad.id),
            meta_ad_id=published_ad.meta_ad_id,
            actor_id=str(actor.id),
        )
        return {
            "published_ad_id": str(published_ad.id),
            "meta_ad_id": published_ad.meta_ad_id,
            "status": "ACTIVE",
            "activated_at": now.isoformat(),
            "activated_by": str(actor.id),
        }

    # ─────────────────────────────────────────────────────────────
    # PAUSE
    # ─────────────────────────────────────────────────────────────

    async def pause(
        self,
        *,
        db: AsyncSession,
        published_ad: PublishedAd,
        actor: User,
        org_id: uuid.UUID,
        emergency: bool = False,
    ) -> dict[str, Any]:
        """Pause an active ad. emergency=True uses minimal pre-conditions."""
        s = self._settings

        if not emergency and actor.role not in ("owner", "admin"):
            return {
                "error": f"Pause requires role 'owner' or 'admin'; current role is '{actor.role}'.",
                "blocked": True,
            }

        if not published_ad.meta_ad_id:
            return {"error": "No meta_ad_id to pause.", "blocked": True}

        from packages.meta_client.publish.write_client_real import RealMetaWriteClient

        client = RealMetaWriteClient(
            access_token=s.meta_access_token,
            app_secret=s.meta_app_secret,
            api_version=s.meta_graph_api_version,
            max_retries=s.meta_write_max_retries,  # pause is idempotent
            timeout_s=s.meta_write_timeout_s,
        )

        action_name = "emergency_pause" if emergency else "pause"
        db.add(AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action=f"{action_name}_intent",
            entity_type="published_ad",
            entity_id=str(published_ad.id),
            payload={"meta_ad_id": published_ad.meta_ad_id},
            result="in_progress",
            dry_run=False,
            emergency=emergency,
        ))
        await db.flush()

        try:
            body, req_id = await client.update_ad_status(published_ad.meta_ad_id, "PAUSED")
        except Exception as exc:
            db.add(AuditLog(
                organization_id=org_id,
                actor_id=actor.id,
                action=f"{action_name}_result",
                entity_type="published_ad",
                entity_id=str(published_ad.id),
                payload={"error": str(exc)},
                result="error",
                dry_run=False,
                emergency=emergency,
                error_detail=str(exc),
            ))
            await db.commit()
            return {"error": str(exc), "meta_ad_id": published_ad.meta_ad_id}

        now = datetime.now(UTC)
        published_ad.status = "PAUSED"
        published_ad.effective_status = "PAUSED"
        published_ad.paused_at = now
        published_ad.paused_by = actor.id

        db.add(AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action=f"{action_name}_result",
            entity_type="published_ad",
            entity_id=str(published_ad.id),
            payload={"meta_ad_id": published_ad.meta_ad_id, "request_id": req_id},
            result="success",
            dry_run=False,
            emergency=emergency,
        ))
        await db.commit()

        logger.info(
            "ad_paused",
            published_ad_id=str(published_ad.id),
            meta_ad_id=published_ad.meta_ad_id,
            emergency=emergency,
            actor_id=str(actor.id),
        )
        return {
            "published_ad_id": str(published_ad.id),
            "meta_ad_id": published_ad.meta_ad_id,
            "status": "PAUSED",
            "emergency": emergency,
            "paused_at": now.isoformat(),
            "paused_by": str(actor.id),
        }
