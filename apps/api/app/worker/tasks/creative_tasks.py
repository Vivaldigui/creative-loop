"""
Celery tasks for creative generation — Phase 1 stubs.
Full implementation in Phase 3 (analysis) and Phase 4 (generation).
"""
from __future__ import annotations

import structlog

from app.worker.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="tasks.analyze_ad", bind=True, max_retries=3)
def analyze_ad_task(self, source_ad_id: str, org_id: str) -> dict:
    """Stub: trigger async analysis of a source ad. Full impl in Phase 3."""
    logger.info("analyze_ad_task_stub", source_ad_id=source_ad_id)
    return {"status": "queued", "source_ad_id": source_ad_id, "note": "Phase 3 will implement real analysis."}


@celery_app.task(name="tasks.generate_creative", bind=True, max_retries=3)
def generate_creative_task(self, prompt_version_id: str, org_id: str) -> dict:
    """Stub: generate creative from a prompt version. Full impl in Phase 4."""
    logger.info("generate_creative_task_stub", prompt_version_id=prompt_version_id)
    return {"status": "queued", "prompt_version_id": prompt_version_id, "note": "Phase 4 will implement real generation."}
