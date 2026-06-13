"""
Celery task for real Meta publish (Phase 6).

Runs the real-publish workflow in the background so the HTTP endpoint can
return 202 immediately.  The caller polls /publication-attempts/{id}/status.

SAFETY RULES (also enforced by service layer):
- Never creates an ACTIVE ad
- Never auto-retries non-idempotent ops (reconciliation handles resume)
- Never logs access_token or app_secret
"""
from __future__ import annotations

import asyncio
import uuid as _uuid

import structlog

from app.worker.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="tasks.publish_real",
    bind=True,
    max_retries=0,           # no automatic retry; reconciliation handles partial failures
    acks_late=True,          # ack only after success/failure (at-least-once delivery)
    reject_on_worker_lost=True,
)
def publish_real_task(
    self,
    *,
    org_id: str,
    creative_id: str,
    actor_id: str,
    attempt_id: str,
    published_ad_id: str,
    idempotency_key: str,
    idempotency_tag: str,
    correlation_id: str,
    # All fields needed to reconstruct MetaPublishPayload via build_payload()
    campaign_name: str,
    adset_name: str,
    ad_name: str,
    objective: str,
    optimization_goal: str,
    billing_event: str,
    bid_strategy: str,
    daily_budget_brl: float,
    landing_url: str,
    headline: str | None = None,
    body_text: str | None = None,
    cta_type: str = "SHOP_NOW",
    targeting: dict | None = None,
    placements: list | None = None,
    promoted_object: dict | None = None,
    tracking_params: dict | None = None,
    # Image bytes (hex-encoded to survive JSON serialisation)
    image_bytes_hex: str = "",
    experiment_id: str | None = None,
    draft_id: str | None = None,
) -> dict:
    """
    Background real-publish task.

    The router already created the PublicationAttempt (result='in_progress')
    and PublishedAd before dispatching this task.  This task drives the
    workflow and updates the records on completion.
    """
    try:
        result = asyncio.run(
            _run_publish(
                org_id=org_id,
                creative_id=creative_id,
                actor_id=actor_id,
                attempt_id=attempt_id,
                published_ad_id=published_ad_id,
                idempotency_key=idempotency_key,
                idempotency_tag=idempotency_tag,
                correlation_id=correlation_id,
                campaign_name=campaign_name,
                adset_name=adset_name,
                ad_name=ad_name,
                objective=objective,
                optimization_goal=optimization_goal,
                billing_event=billing_event,
                bid_strategy=bid_strategy,
                daily_budget_brl=daily_budget_brl,
                landing_url=landing_url,
                headline=headline,
                body_text=body_text,
                cta_type=cta_type,
                targeting=targeting,
                placements=placements,
                promoted_object=promoted_object,
                tracking_params=tracking_params,
                image_bytes=bytes.fromhex(image_bytes_hex) if image_bytes_hex else b"",
                experiment_id=experiment_id,
                draft_id=draft_id,
            )
        )
        return result
    except Exception as exc:
        logger.error(
            "publish_real_task_unhandled_error",
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            error=str(exc),
            exc_info=True,
        )
        # Do NOT retry — mark attempt as failed
        asyncio.run(_mark_attempt_failed(attempt_id, str(exc)))
        raise


async def _run_publish(
    *,
    org_id: str,
    creative_id: str,
    actor_id: str,
    attempt_id: str,
    published_ad_id: str,
    idempotency_key: str,
    idempotency_tag: str,
    correlation_id: str,
    campaign_name: str,
    adset_name: str,
    ad_name: str,
    objective: str,
    optimization_goal: str,
    billing_event: str,
    bid_strategy: str,
    daily_budget_brl: float,
    landing_url: str,
    headline: str | None,
    body_text: str | None,
    cta_type: str,
    targeting: dict | None,
    placements: list | None,
    promoted_object: dict | None,
    tracking_params: dict | None,
    image_bytes: bytes,
    experiment_id: str | None,
    draft_id: str | None,
) -> dict:
    from packages.meta_client.publish.real_publisher import RealPublisher
    from packages.meta_client.publish.write_client_real import RealMetaWriteClient
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import get_session_factory
    from app.models.creative import GeneratedCreative
    from app.models.publication import PublicationAttempt
    from app.models.publish import PublicationStep, PublishedAd
    from app.services.publication_service import PublicationService

    s = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as db:
        creative = (await db.execute(
            select(GeneratedCreative).where(GeneratedCreative.id == _uuid.UUID(creative_id))
        )).scalar_one()

        attempt = (await db.execute(
            select(PublicationAttempt).where(PublicationAttempt.id == _uuid.UUID(attempt_id))
        )).scalar_one()

        published_ad = (await db.execute(
            select(PublishedAd).where(PublishedAd.id == _uuid.UUID(published_ad_id))
        )).scalar_one_or_none()

        # Rebuild MetaPublishPayload from individual fields
        svc = PublicationService(s)
        payload = svc.build_payload(
            creative=creative,
            campaign_name=campaign_name,
            adset_name=adset_name,
            ad_name=ad_name,
            objective=objective,
            optimization_goal=optimization_goal,
            billing_event=billing_event,
            bid_strategy=bid_strategy,
            daily_budget_brl=daily_budget_brl,
            landing_url=landing_url,
            headline=headline,
            body_text=body_text,
            cta_type=cta_type,
            targeting=targeting,
            placements=placements,
            promoted_object=promoted_object,
            tracking_params=tracking_params,
        )

        # Inject image bytes via __setattr__ bypass (Pydantic does not allow extra fields)
        object.__setattr__(payload.image_upload, "_raw_bytes", image_bytes)

        client = RealMetaWriteClient(
            access_token=s.meta_access_token,
            app_secret=s.meta_app_secret,
            api_version=s.meta_graph_api_version,
            max_retries=s.meta_write_max_retries,
            timeout_s=s.meta_write_timeout_s,
        )
        publisher = RealPublisher(client=client, idempotency_tag=idempotency_tag)
        pub_result = await publisher.publish(payload, correlation_id=correlation_id)

        # Persist steps
        meta_request_ids: dict[str, str] = {}
        for step in pub_result.steps:
            ps = PublicationStep(
                organization_id=_uuid.UUID(org_id),
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

        # Update PublishedAd
        final_result = "published" if pub_result.succeeded else pub_result.workflow_state
        if published_ad:
            published_ad.meta_campaign_id = pub_result.meta_campaign_id
            published_ad.meta_adset_id = pub_result.meta_adset_id
            published_ad.meta_image_hash = pub_result.meta_image_hash
            published_ad.meta_creative_id = pub_result.meta_creative_id
            published_ad.meta_ad_id = pub_result.meta_ad_id
            published_ad.workflow_state = pub_result.workflow_state
            published_ad.status = "PAUSED" if pub_result.succeeded else pub_result.workflow_state
            published_ad.error_detail = pub_result.error_detail

        # Update PublicationAttempt
        attempt.result = final_result
        attempt.meta_request_ids = meta_request_ids
        if pub_result.error_detail:
            attempt.error_detail = pub_result.error_detail

        await db.commit()

        logger.info(
            "publish_real_task_complete",
            attempt_id=attempt_id,
            workflow_state=pub_result.workflow_state,
            meta_ad_id=pub_result.meta_ad_id,
            correlation_id=correlation_id,
        )

        return {
            "attempt_id": attempt_id,
            "published_ad_id": published_ad_id,
            "workflow_state": pub_result.workflow_state,
            "meta_ad_id": pub_result.meta_ad_id,
            "result": final_result,
            "error_detail": pub_result.error_detail,
            "requires_manual_review": pub_result.requires_manual_review,
        }


async def _mark_attempt_failed(attempt_id: str, error_detail: str) -> None:
    from sqlalchemy import select

    from app.db import get_session_factory
    from app.models.publication import PublicationAttempt

    session_factory = get_session_factory()
    async with session_factory() as db:
        attempt = (await db.execute(
            select(PublicationAttempt).where(PublicationAttempt.id == _uuid.UUID(attempt_id))
        )).scalar_one_or_none()
        if attempt:
            attempt.result = "failed"
            attempt.error_detail = error_detail
            await db.commit()
