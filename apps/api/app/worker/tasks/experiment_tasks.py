"""
Celery tasks for Phase 7 experiment pipeline.

All tasks are idempotent: running twice produces the same final state.
Timezone: America/Sao_Paulo (set in celery_app.conf.timezone).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, timedelta

import structlog

from app.config import get_settings
from app.worker.celery_app import celery_app

logger = structlog.get_logger()


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Metric collection ──────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.collect_variant_metrics",
    bind=True,
    max_retries=0,
    ignore_result=False,
    acks_late=True,
)
def collect_variant_metrics(self, experiment_id: str, org_id: str, days_back: int = 30) -> dict:
    """
    Collect Meta metrics for all variants in one experiment.
    Idempotent via UniqueConstraint upsert.
    """
    return _run(_collect_variant_metrics_async(experiment_id, org_id, days_back))


async def _collect_variant_metrics_async(experiment_id: str, org_id: str, days_back: int) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.services.metric_collection_service import MetricCollectionService

    settings = get_settings()
    engine = get_engine()
    async with AsyncSession(engine) as db:
        svc = MetricCollectionService(settings)
        result = await svc.collect_for_experiment(
            db=db,
            org_id=uuid.UUID(org_id),
            experiment_id=uuid.UUID(experiment_id),
            days_back=days_back,
        )
    logger.info("collect_variant_metrics.done", experiment_id=experiment_id, **result)
    return result


@celery_app.task(
    name="tasks.dispatch_metric_collection",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def dispatch_metric_collection(self) -> dict:
    """
    Fan-out: find all running experiments and enqueue collect_variant_metrics for each.
    Beat schedule: every hour.
    """
    return _run(_dispatch_metric_collection_async())


async def _dispatch_metric_collection_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.experiment import Experiment

    engine = get_engine()
    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(Experiment.id, Experiment.organization_id).where(
                Experiment.status.in_(["running", "evaluating"])
            )
        )
        rows = result.all()

    dispatched = 0
    for exp_id, org_id in rows:
        collect_variant_metrics.delay(str(exp_id), str(org_id))
        dispatched += 1

    logger.info("dispatch_metric_collection.done", dispatched=dispatched)
    return {"dispatched": dispatched}


# ── Evaluation ────────────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.compute_evaluations",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def compute_evaluations(self) -> dict:
    """
    Run evaluations for all running/evaluating experiments.
    Beat schedule: every 6 hours.
    Append-only: each call creates a new ExperimentEvaluation row.
    """
    return _run(_compute_evaluations_async())


async def _compute_evaluations_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.experiment import Experiment
    from app.services.evaluation_service import EvaluationService

    settings = get_settings()
    engine = get_engine()
    evaluated = 0
    errors = 0

    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(Experiment).where(
                Experiment.status.in_(["running", "evaluating"])
            )
        )
        experiments = result.scalars().all()

    for exp in experiments:
        try:
            engine2 = get_engine()
            async with AsyncSession(engine2) as db2:
                svc = EvaluationService(settings)
                # Use a system actor ID (zero UUID) for automated evaluations
                await svc.evaluate(
                    db=db2,
                    org_id=exp.organization_id,
                    actor_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    experiment_id=exp.id,
                    notes="Automated evaluation by Beat worker",
                )
            evaluated += 1
        except Exception as e:
            errors += 1
            logger.warning("compute_evaluations.error", experiment_id=str(exp.id), error=str(e))

    logger.info("compute_evaluations.done", evaluated=evaluated, errors=errors)
    return {"evaluated": evaluated, "errors": errors}


# ── Anomaly detection ──────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.detect_anomalous_spend",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def detect_anomalous_spend(self) -> dict:
    """
    Detect variants with anomalous spend (>Nx rolling median).
    Beat schedule: every 4 hours.
    Writes AuditLog entries but does NOT change budgets automatically.
    """
    return _run(_detect_anomalous_spend_async())


async def _detect_anomalous_spend_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.audit import AuditLog
    from app.models.variant_metric import VariantPerformanceSnapshot

    settings = get_settings()
    engine = get_engine()
    anomalies = 0

    async with AsyncSession(engine) as db:
        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        today_str = today.isoformat()

        result = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.date_start >= yesterday,
                VariantPerformanceSnapshot.date_stop <= today_str,
                VariantPerformanceSnapshot.spend.isnot(None),
            )
        )
        snaps = result.scalars().all()

        # Compute per-org rolling median
        from collections import defaultdict
        by_org: dict[str, list[float]] = defaultdict(list)
        for s in snaps:
            if s.spend:
                by_org[str(s.organization_id)].append(s.spend)

        for org_key, spends in by_org.items():
            if not spends:
                continue
            sorted_spends = sorted(spends)
            mid = len(sorted_spends) // 2
            median = sorted_spends[mid] if len(sorted_spends) % 2 else (sorted_spends[mid - 1] + sorted_spends[mid]) / 2
            threshold = median * settings.anomalous_spend_multiplier

            for s in snaps:
                if str(s.organization_id) != org_key:
                    continue
                if s.spend and s.spend > threshold:
                    log = AuditLog(
                        organization_id=s.organization_id,
                        actor_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                        action="anomalous_spend_detected",
                        entity_type="variant_performance_snapshot",
                        entity_id=str(s.id),
                        payload={
                            "spend": s.spend,
                            "median": median,
                            "multiplier": settings.anomalous_spend_multiplier,
                            "threshold": threshold,
                            "auto_budget_change": False,
                        },
                        result="alert",
                    )
                    db.add(log)
                    anomalies += 1

        await db.commit()

    logger.info("detect_anomalous_spend.done", anomalies=anomalies)
    return {"anomalies_detected": anomalies}


@celery_app.task(
    name="tasks.detect_zero_conversions",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def detect_zero_conversions(self) -> dict:
    """
    Flag running experiment variants with spend > 10 and 0 conversions.
    Beat schedule: every 12 hours.
    Writes AuditLog. Does NOT pause campaigns automatically.
    """
    return _run(_detect_zero_conversions_async())


async def _detect_zero_conversions_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.audit import AuditLog
    from app.models.variant_metric import VariantPerformanceSnapshot

    engine = get_engine()
    flagged = 0

    async with AsyncSession(engine) as db:
        today_str = date.today().isoformat()
        week_ago = (date.today() - timedelta(days=7)).isoformat()

        result = await db.execute(
            select(VariantPerformanceSnapshot).where(
                VariantPerformanceSnapshot.date_start >= week_ago,
                VariantPerformanceSnapshot.date_stop <= today_str,
                VariantPerformanceSnapshot.spend > 10.0,
            )
        )
        for snap in result.scalars().all():
            purchases = snap.purchases or 0
            leads = snap.leads or 0
            if purchases == 0 and leads == 0:
                log = AuditLog(
                    organization_id=snap.organization_id,
                    actor_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    action="zero_conversions_detected",
                    entity_type="variant_performance_snapshot",
                    entity_id=str(snap.id),
                    payload={
                        "spend": snap.spend,
                        "purchases": purchases,
                        "leads": leads,
                        "date_range": f"{snap.date_start}/{snap.date_stop}",
                        "auto_pause": False,
                    },
                    result="alert",
                )
                db.add(log)
                flagged += 1

        await db.commit()

    logger.info("detect_zero_conversions.done", flagged=flagged)
    return {"flagged": flagged}


@celery_app.task(
    name="tasks.detect_rejected_ads",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def detect_rejected_ads(self) -> dict:
    """
    Flag published ads with DISAPPROVED status.
    Beat schedule: every 6 hours.
    """
    return _run(_detect_rejected_ads_async())


async def _detect_rejected_ads_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.audit import AuditLog
    from app.models.publish import PublishedAd

    engine = get_engine()
    flagged = 0

    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(PublishedAd).where(PublishedAd.effective_status == "DISAPPROVED")
        )
        for pad in result.scalars().all():
            log = AuditLog(
                organization_id=pad.organization_id,
                actor_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                action="rejected_ad_detected",
                entity_type="published_ad",
                entity_id=str(pad.id),
                payload={"meta_ad_id": pad.meta_ad_id, "effective_status": pad.effective_status},
                result="alert",
            )
            db.add(log)
            flagged += 1

        await db.commit()

    logger.info("detect_rejected_ads.done", flagged=flagged)
    return {"flagged": flagged}


# ── Experiment status updates ──────────────────────────────────────────────────

@celery_app.task(
    name="tasks.update_experiment_status",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def update_experiment_status(self) -> dict:
    """
    Transition experiments that have passed their window_end to 'evaluating'.
    Beat schedule: daily at 01:00.
    Idempotent: only transitions running → evaluating when window_end < now.
    """
    return _run(_update_experiment_status_async())


async def _update_experiment_status_async() -> dict:
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.experiment import Experiment

    engine = get_engine()
    transitioned = 0

    async with AsyncSession(engine) as db:
        now = datetime.now(UTC)
        result = await db.execute(
            select(Experiment).where(
                Experiment.status == "running",
                Experiment.window_end.isnot(None),
                Experiment.window_end < now,
            )
        )
        for exp in result.scalars().all():
            exp.status = "evaluating"
            transitioned += 1

        await db.commit()

    logger.info("update_experiment_status.done", transitioned=transitioned)
    return {"transitioned": transitioned}


@celery_app.task(
    name="tasks.flag_experiments_ready",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def flag_experiments_ready(self) -> dict:
    """
    Flag experiments with enough matured data as ready for evaluation.
    Beat schedule: every 12 hours.
    """
    return _run(_flag_experiments_ready_async())


async def _flag_experiments_ready_async() -> dict:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.experiment import Experiment
    from app.models.variant_metric import VariantPerformanceSnapshot

    settings = get_settings()
    engine = get_engine()
    flagged = 0

    async with AsyncSession(engine) as db:
        result = await db.execute(
            select(Experiment).where(Experiment.status == "running")
        )
        for exp in result.scalars().all():
            count_result = await db.execute(
                select(func.count(VariantPerformanceSnapshot.id)).where(
                    VariantPerformanceSnapshot.experiment_id == exp.id,
                    VariantPerformanceSnapshot.is_matured == True,  # noqa: E712
                )
            )
            matured_count = count_result.scalar() or 0
            min_impressions = settings.exp_default_min_impressions

            if exp.min_criteria:
                min_impressions = exp.min_criteria.get("min_impressions", min_impressions)

            if matured_count > 0:
                snap_result = await db.execute(
                    select(func.sum(VariantPerformanceSnapshot.impressions)).where(
                        VariantPerformanceSnapshot.experiment_id == exp.id,
                        VariantPerformanceSnapshot.is_matured == True,  # noqa: E712
                    )
                )
                total_impressions = snap_result.scalar() or 0

                if total_impressions >= min_impressions:
                    flagged += 1

        await db.commit()

    logger.info("flag_experiments_ready.done", flagged=flagged)
    return {"ready": flagged}


# ── Reports ────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.daily_report",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def daily_report(self) -> dict:
    """
    Generate and log daily report for all orgs.
    Beat schedule: daily at 08:00 America/Sao_Paulo.
    """
    return _run(_daily_report_async())


async def _daily_report_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.organization import Organization
    from app.services.report_service import ReportService

    settings = get_settings()
    engine = get_engine()
    reports_generated = 0

    async with AsyncSession(engine) as db:
        result = await db.execute(select(Organization.id))
        org_ids = result.scalars().all()

    svc = ReportService(settings)
    for org_id in org_ids:
        try:
            engine2 = get_engine()
            async with AsyncSession(engine2) as db2:
                report = await svc.daily(db2, org_id)
            if report.alerts:
                logger.warning(
                    "daily_report.alerts",
                    org_id=str(org_id),
                    alert_count=len(report.alerts),
                    alerts=[a.code for a in report.alerts],
                )
            reports_generated += 1
        except Exception as e:
            logger.error("daily_report.error", org_id=str(org_id), error=str(e))

    logger.info("daily_report.done", reports_generated=reports_generated)
    return {"reports_generated": reports_generated}


@celery_app.task(
    name="tasks.weekly_report",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def weekly_report(self) -> dict:
    """
    Generate and log weekly report for all orgs.
    Beat schedule: Mondays at 08:00 America/Sao_Paulo.
    """
    return _run(_weekly_report_async())


async def _weekly_report_async() -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.models.organization import Organization
    from app.services.report_service import ReportService

    settings = get_settings()
    engine = get_engine()
    reports_generated = 0

    async with AsyncSession(engine) as db:
        result = await db.execute(select(Organization.id))
        org_ids = result.scalars().all()

    svc = ReportService(settings)
    for org_id in org_ids:
        try:
            engine2 = get_engine()
            async with AsyncSession(engine2) as db2:
                report = await svc.weekly(db2, org_id)
            logger.info(
                "weekly_report.generated",
                org_id=str(org_id),
                completed_experiments=len(report.completed_experiments),
                new_learnings=len(report.new_learnings),
            )
            reports_generated += 1
        except Exception as e:
            logger.error("weekly_report.error", org_id=str(org_id), error=str(e))

    logger.info("weekly_report.done", reports_generated=reports_generated)
    return {"reports_generated": reports_generated}


# ── Next-round suggestion ──────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.suggest_next_round",
    bind=True,
    max_retries=0,
    acks_late=True,
)
def suggest_next_round(self, experiment_id: str, org_id: str, actor_id: str | None = None) -> dict:
    """
    Create a next-round suggestion for a completed experiment.
    Requires human approval before any downstream action.
    Does NOT generate images or publish automatically.
    """
    return _run(_suggest_next_round_async(experiment_id, org_id, actor_id))


async def _suggest_next_round_async(experiment_id: str, org_id: str, actor_id: str | None) -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import get_engine
    from app.services.next_round_service import NextRoundService

    settings = get_settings()
    engine = get_engine()
    _actor_id = uuid.UUID(actor_id) if actor_id else uuid.UUID("00000000-0000-0000-0000-000000000000")

    try:
        async with AsyncSession(engine) as db:
            svc = NextRoundService(settings)
            suggestion = await svc.suggest(
                db=db,
                org_id=uuid.UUID(org_id),
                actor_id=_actor_id,
                experiment_id=uuid.UUID(experiment_id),
            )
        logger.info(
            "suggest_next_round.done",
            suggestion_id=str(suggestion.id),
            experiment_id=experiment_id,
            auto_image_generation=False,
            auto_publish=False,
        )
        return {"suggestion_id": str(suggestion.id), "status": suggestion.status}
    except ValueError as e:
        logger.warning("suggest_next_round.skipped", experiment_id=experiment_id, reason=str(e))
        return {"skipped": True, "reason": str(e)}
