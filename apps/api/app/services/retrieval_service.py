"""
LearningRetrievalService — queries learnings with multi-factor scoring.

Score = relevance_structural × confidence_weight × recency − λ × diversity_penalty
"""
from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.learning import Learning

# Status weights
_STATUS_WEIGHT = {"confirmed": 1.0, "provisional": 0.6, "rejected": 0.0}
# Recency half-life in days
_RECENCY_HALF_LIFE_DAYS = 60


class LearningRetrievalService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def query(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        product_id: uuid.UUID | None = None,
        segment: str | None = None,
        objective: str | None = None,
        placement: str | None = None,
        format: str | None = None,
        audience: dict[str, Any] | None = None,
        reference_text: str | None = None,
        include_provisional: bool = True,
        max_results: int | None = None,
        existing_learning_ids: list[str] | None = None,
    ) -> list[Learning]:
        """
        Returns scored learnings, most relevant first.
        rejected learnings are always excluded.
        """
        limit = max_results or self._settings.exp_retrieval_max_results

        q = select(Learning).where(
            Learning.organization_id == org_id,
            Learning.status != "rejected",
        )
        if not include_provisional:
            q = q.where(Learning.status == "confirmed")
        if product_id:
            q = q.where(Learning.product_id == product_id)

        rows = (await db.execute(q)).scalars().all()

        # Score each
        scored: list[tuple[float, Learning]] = []
        ref_embedding = _mock_embedding(reference_text) if reference_text else None

        for learning in rows:
            score = _score_learning(
                learning=learning,
                segment=segment,
                objective=objective,
                placement=placement,
                format=format,
                ref_embedding=ref_embedding,
                existing_learning_ids=existing_learning_ids or [],
            )
            if score > 0.0:
                scored.append((score, learning))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [lr for _, lr in scored[:limit]]

    async def compute_diversity_score(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        candidate_prompt_hash: str | None,
        candidate_phash: str | None,
        variation_depth: int = 0,
        selected_learning_ids: list[str] | None = None,
    ) -> float:
        """Compute diversity score for a candidate suggestion."""
        from packages.experiment_engine.diversity_scorer import DiversityScorer

        from app.models.creative import GeneratedCreative
        from app.models.prompt import PromptVersion

        # Get existing prompt hashes for this org
        pv_result = await db.execute(
            select(PromptVersion.content_hash).where(
                PromptVersion.organization_id == org_id,
                PromptVersion.content_hash.isnot(None),
            ).limit(100)
        )
        existing_hashes = [r for r in pv_result.scalars().all() if r]

        # Get existing phashes
        phash_result = await db.execute(
            select(GeneratedCreative.phash).where(
                GeneratedCreative.organization_id == org_id,
                GeneratedCreative.phash.isnot(None),
            ).limit(100)
        )
        existing_phashes = [r for r in phash_result.scalars().all() if r]

        # Compute max reuse count across selected learnings
        max_reuse = 0
        if selected_learning_ids:
            from app.models.learning import LearningUsage
            for lid in selected_learning_ids:
                try:
                    lid_uuid = uuid.UUID(lid)
                except ValueError:
                    continue
                reuse_result = await db.execute(
                    select(LearningUsage).where(LearningUsage.learning_id == lid_uuid).limit(50)
                )
                count = len(reuse_result.scalars().all())
                max_reuse = max(max_reuse, count)

        scorer = DiversityScorer()
        result = scorer.score(
            candidate_prompt_hash=candidate_prompt_hash,
            existing_prompt_hashes=existing_hashes,
            candidate_phash=candidate_phash,
            existing_phashes=existing_phashes,
            variation_depth=variation_depth,
            learning_reuse_count=max_reuse,
            max_variation_depth=self._settings.exp_max_variation_depth,
            max_learning_reuse=self._settings.exp_max_learning_reuse,
        )
        return result.score


# ── Scoring helpers ────────────────────────────────────────────────────────────

def _score_learning(
    learning: Learning,
    segment: str | None,
    objective: str | None,
    placement: str | None,
    format: str | None,
    ref_embedding: list[float] | None,
    existing_learning_ids: list[str],
) -> float:
    score = 0.0

    # Structural match
    structural = 0.0
    if segment and learning.segment == segment:
        structural += 0.3
    if objective and learning.objective == objective:
        structural += 0.3
    if placement and learning.placement == placement:
        structural += 0.2
    if format and learning.format == format:
        structural += 0.2
    score += structural

    # Status confidence weight
    status_w = _STATUS_WEIGHT.get(learning.status, 0.0)
    if status_w == 0.0:
        return 0.0
    conf_w = (learning.confidence or 0.5) * status_w
    score *= (0.5 + conf_w)

    # Recency decay
    age_days = _age_days(learning)
    recency = math.exp(-math.log(2) * age_days / _RECENCY_HALF_LIFE_DAYS)
    score *= (0.5 + 0.5 * recency)

    # Semantic similarity bonus
    if ref_embedding and learning.embedding:
        sim = _cosine_similarity(ref_embedding, learning.embedding)
        score += 0.2 * max(0.0, sim)

    # Diversity penalty for already-used learnings
    if str(learning.id) in existing_learning_ids:
        score *= 0.5

    return max(0.0, score)


def _age_days(learning: Learning) -> float:
    if not learning.created_at:
        return 0.0
    now = datetime.now(UTC)
    created = learning.created_at
    if created.tzinfo is None:
        import pytz  # type: ignore[import]
        created = pytz.utc.localize(created)
    delta = now - created
    return max(0.0, delta.total_seconds() / 86400.0)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x ** 2 for x in a)) or 1.0
    norm_b = math.sqrt(sum(x ** 2 for x in b)) or 1.0
    return dot / (norm_a * norm_b)


def _mock_embedding(text: str) -> list[float]:
    import hashlib
    digest = hashlib.sha256(text.encode()).digest()
    floats = [(b / 127.5) - 1.0 for b in digest]
    while len(floats) < 128:
        floats.extend(floats[:128 - len(floats)])
    floats = floats[:128]
    norm = sum(f ** 2 for f in floats) ** 0.5 or 1.0
    return [f / norm for f in floats]
