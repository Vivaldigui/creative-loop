from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "creative_loop",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone=settings.default_timezone,  # America/Sao_Paulo
        enable_utc=True,
        task_always_eager=False,
        beat_schedule={
            # ── Phase 2/3 ────────────────────────────────────────────
            "meta-incremental-hourly": {
                "task": "tasks.dispatch_meta_incremental_syncs",
                "schedule": 3600.0,
            },
            # ── Phase 7: metric collection (every hour) ───────────────
            "dispatch-metric-collection-hourly": {
                "task": "tasks.dispatch_metric_collection",
                "schedule": 3600.0,
            },
            # ── Phase 7: evaluation (every 6h) ───────────────────────
            "compute-evaluations-6h": {
                "task": "tasks.compute_evaluations",
                "schedule": 21600.0,
            },
            # ── Phase 7: anomalous spend (every 4h) ──────────────────
            "detect-anomalous-spend-4h": {
                "task": "tasks.detect_anomalous_spend",
                "schedule": 14400.0,
            },
            # ── Phase 7: zero conversions (every 12h) ────────────────
            "detect-zero-conversions-12h": {
                "task": "tasks.detect_zero_conversions",
                "schedule": 43200.0,
            },
            # ── Phase 7: rejected ads (every 6h) ─────────────────────
            "detect-rejected-ads-6h": {
                "task": "tasks.detect_rejected_ads",
                "schedule": 21600.0,
            },
            # ── Phase 7: experiment status update (daily 01:00 SP) ───
            "update-experiment-status-daily": {
                "task": "tasks.update_experiment_status",
                "schedule": crontab(hour=1, minute=0),
            },
            # ── Phase 7: flag experiments ready (every 12h) ──────────
            "flag-experiments-ready-12h": {
                "task": "tasks.flag_experiments_ready",
                "schedule": 43200.0,
            },
            # ── Phase 7: daily report (08:00 SP) ─────────────────────
            "daily-report-0800": {
                "task": "tasks.daily_report",
                "schedule": crontab(hour=settings.daily_report_hour, minute=0),
            },
            # ── Phase 7: weekly report (Monday 08:00 SP) ─────────────
            "weekly-report-monday-0800": {
                "task": "tasks.weekly_report",
                "schedule": crontab(
                    hour=settings.daily_report_hour,
                    minute=0,
                    day_of_week=settings.weekly_report_day,
                ),
            },
        },
    )
    # autodiscover_tasks(packages, related_name="tasks") imports <package>.tasks
    # So pass the parent package so it imports app.worker.tasks, whose __init__
    # imports the four task submodules and registers all Celery tasks.
    app.autodiscover_tasks(["app.worker"])
    return app


celery_app = make_celery()
