"""
Analysis service (Phase 3).

Orchestrates:
  1. Load SourceAd + aggregate metrics
  2. Detect media kind
  3. Compute input_hash for idempotency
  4. Skip if same analysis already exists (unless force=True)
  5. AuditLog pre-action
  6. Call provider (mock or real)
  7. Persist CreativeAnalysis with full metadata
  8. AuditLog post-action (no image, no copy, no tokens in logs)
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.analysis import CreativeAnalysis
from app.models.audit import AuditLog
from app.models.source_ad import PerformanceSnapshot, SourceAd

logger = structlog.get_logger()


class AnalysisService:
    def __init__(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        *,
        provider: str = "mock",
        model: str = "claude-sonnet-4-6",
        timeout_s: float = 60.0,
        max_retries: int = 3,
        max_image_bytes: int = 5 * 1_048_576,
        price_input_per_mtok: float | None = None,
        price_output_per_mtok: float | None = None,
    ) -> None:
        self._db = db
        self._org_id = org_id
        self._actor_id = actor_id
        self._provider = provider
        self._model = model
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._max_image_bytes = max_image_bytes
        self._price_in = price_input_per_mtok
        self._price_out = price_output_per_mtok

    async def analyze(
        self,
        ad_id: uuid.UUID,
        force: bool = False,
    ) -> CreativeAnalysis:
        """Run analysis for the given SourceAd. Returns the CreativeAnalysis row."""
        from packages.anthropic_client.factory import get_anthropic_client
        from packages.anthropic_client.image_guard import detect_media_kind
        from packages.anthropic_client.interface import AnalysisRequest

        # 1. Load ad with snapshots (org-scoped)
        result = await self._db.execute(
            select(SourceAd)
            .where(SourceAd.id == ad_id, SourceAd.organization_id == self._org_id)
            .options(selectinload(SourceAd.snapshots))
        )
        ad = result.scalar_one_or_none()
        if ad is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Ad not found")

        # 2. Aggregate metrics across all snapshots
        metrics = _aggregate_metrics(ad.snapshots)

        # 3. Detect media kind
        media_kind = detect_media_kind(ad.image_path, ad.image_url)

        # 4. Build request (copy is safe to hash; provider sanitises before sending)
        request = AnalysisRequest(
            ad_name=ad.name,
            headline=ad.headline,
            body_text=ad.body_text,
            cta=ad.cta,
            image_path=ad.image_path,
            image_url=ad.image_url,
            metrics=metrics,
        )

        # 5. Compute input_hash
        input_hash = _compute_input_hash(
            model=self._model,
            provider=self._provider,
            image_path=ad.image_path,
            metrics=metrics,
            request_fields={
                "ad_name": ad.name,
                "headline": ad.headline,
                "body_text": ad.body_text,
                "cta": ad.cta,
            },
        )

        # 6. Idempotency check
        if not force:
            existing = await self._find_existing(ad_id, input_hash)
            if existing is not None:
                logger.info(
                    "analysis_idempotent_hit",
                    analysis_id=str(existing.id),
                    ad_id=str(ad_id),
                )
                return existing

        # 7. Determine analysis_version
        version = await self._next_version(ad_id)

        # 8. AuditLog — pending (before call, no image/copy content)
        audit = AuditLog(
            organization_id=self._org_id,
            actor_id=self._actor_id,
            action="analyze_ad",
            entity_type="source_ad",
            entity_id=str(ad_id),
            payload={
                "provider": self._provider,
                "model": self._model,
                "had_image": bool(ad.image_path),
                "media_kind": media_kind,
                "force": force,
                "analysis_version": version,
            },
            result="pending",
            dry_run=False,
        )
        self._db.add(audit)
        await self._db.flush()

        # 9. Call provider
        client = get_anthropic_client(
            provider=self._provider,
            api_key=_get_api_key(self._provider),
            model=self._model,
            max_image_bytes=self._max_image_bytes,
            price_input_per_mtok=self._price_in,
            price_output_per_mtok=self._price_out,
        )

        envelope = None
        error_detail: str | None = None
        try:
            envelope = await client.analyze(
                request,
                timeout=self._timeout_s,
                max_retries=self._max_retries,
            )
            audit.result = "success"
        except Exception as exc:
            error_detail = str(exc)
            audit.result = "error"
            audit.error_detail = error_detail
            await self._db.commit()
            raise

        r = envelope.result
        s = r.to_storage_dict()

        analysis = CreativeAnalysis(
            organization_id=self._org_id,
            source_ad_id=ad_id,
            provider=self._provider,
            model_used=envelope.model_used,
            status=envelope.status,
            input_hash=input_hash,
            analysis_version=version,
            media_kind=media_kind,
            is_fictitious=ad.is_fictitious,
            repaired=envelope.repaired,
            error_detail=envelope.error_detail,
            # Core structured fields
            visual_summary=r.visual_summary,
            observations={"items": s["observations"]},
            metric_facts={"items": s["metric_facts"]},
            limitations={"items": s["limitations"]},
            composition=s["composition"],
            hierarchy=s["hierarchy"],
            product_presentation=s["product_presentation"],
            color_and_lighting=s["color_and_lighting"],
            text_analysis=s["text_analysis"],
            attention_elements={"items": s["attention_elements"]},
            strengths={"items": s["strengths"]},
            weaknesses={"items": s["weaknesses"]},
            performance_hypotheses={"items": list(s["performance_hypotheses"])},
            elements_to_preserve={"items": s["elements_to_preserve"]},
            elements_to_test={"items": s["elements_to_test"]},
            policy_risks={"items": s["policy_risks"]},
            confidence=r.confidence,
            # Call metadata (no image bytes, no API key, no copy)
            request_metadata={
                "had_image": bool(ad.image_path),
                "media_kind": media_kind,
                "n_metrics": len(metrics),
                "n_snapshots": len(ad.snapshots),
            },
            parameters={
                "model": self._model,
                "provider": self._provider,
                "max_tokens": 2048,
                "timeout_s": self._timeout_s,
                "max_retries": self._max_retries,
            },
            prompt_tokens=envelope.usage.input_tokens if envelope.usage else None,
            output_tokens=envelope.usage.output_tokens if envelope.usage else None,
            estimated_cost_usd=envelope.estimated_cost_usd,
            latency_ms=envelope.latency_ms,
        )
        self._db.add(analysis)
        await self._db.commit()
        await self._db.refresh(analysis)
        return analysis

    # ── Internal helpers ──────────────────────────────────────────

    async def _find_existing(
        self, ad_id: uuid.UUID, input_hash: str
    ) -> CreativeAnalysis | None:
        result = await self._db.execute(
            select(CreativeAnalysis).where(
                CreativeAnalysis.organization_id == self._org_id,
                CreativeAnalysis.source_ad_id == ad_id,
                CreativeAnalysis.input_hash == input_hash,
            )
        )
        return result.scalar_one_or_none()

    async def _next_version(self, ad_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.max(CreativeAnalysis.analysis_version)).where(
                CreativeAnalysis.organization_id == self._org_id,
                CreativeAnalysis.source_ad_id == ad_id,
            )
        )
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1


# ── Module-level helpers ──────────────────────────────────────────

def _aggregate_metrics(snapshots: list[PerformanceSnapshot]) -> dict[str, Any]:
    """Sum/average key metrics across all snapshots."""
    if not snapshots:
        return {}

    totals: dict[str, float] = {}
    counts: dict[str, int] = {}

    sum_fields = ["impressions", "reach", "spend", "clicks", "link_clicks",
                  "landing_page_views", "adds_to_cart", "initiate_checkout",
                  "purchases", "leads", "purchase_value"]
    avg_fields = ["frequency", "ctr", "cpc", "cpm", "cost_per_result", "roas"]

    for snap in snapshots:
        for field in sum_fields:
            v = getattr(snap, field, None)
            if v is not None:
                totals[field] = totals.get(field, 0.0) + float(v)
        for field in avg_fields:
            v = getattr(snap, field, None)
            if v is not None:
                totals[field] = totals.get(field, 0.0) + float(v)
                counts[field] = counts.get(field, 0) + 1

    result: dict[str, Any] = {}
    for field in sum_fields:
        if field in totals:
            result[field] = totals[field]
    for field in avg_fields:
        if field in counts and counts[field] > 0:
            result[field] = round(totals[field] / counts[field], 6)

    return result


def _compute_input_hash(
    model: str,
    provider: str,
    image_path: str | None,
    metrics: dict[str, Any],
    request_fields: dict[str, Any],
) -> str:
    """sha256 over (model, provider, image_path, sorted_metrics, sorted_fields)."""
    payload = json.dumps(
        {
            "model": model,
            "provider": provider,
            "image_path": image_path or "",
            "metrics": dict(sorted(metrics.items())),
            "fields": {k: v for k, v in sorted(request_fields.items()) if v is not None},
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_api_key(provider: str) -> str | None:
    if provider != "real":
        return None
    try:
        from app.config import get_settings
        return get_settings().anthropic_api_key
    except Exception:
        return None
