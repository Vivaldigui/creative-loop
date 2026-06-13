"""
LearningService — creates, confirms and rejects structured learnings.

Lifecycle:
    provisional → confirmed  (human review + audit)
    provisional → rejected   (human review + mandatory comment)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.audit import AuditLog
from app.models.learning import Learning
from app.schemas.learning import LearningCreate

logger = structlog.get_logger()


class LearningService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        data: LearningCreate,
    ) -> Learning:
        # Generate a simple mock embedding (deterministic for dev/tests)
        embedding = _mock_embedding(data.observed_pattern)

        learning = Learning(
            organization_id=org_id,
            context=data.context,
            segment=data.segment,
            product_id=data.product_id,
            audience=data.audience,
            placement=data.placement,
            format=data.format,
            objective=data.objective,
            observed_pattern=data.observed_pattern,
            evidence=data.evidence,
            sample_size=data.sample_size,
            metrics=data.metrics,
            limitations=data.limitations,
            confidence=data.confidence,
            source_experiment_id=data.source_experiment_id,
            source_evaluation_id=data.source_evaluation_id,
            period_start=data.period_start,
            period_end=data.period_end,
            status="provisional",
            responsible_type=data.responsible_type,
            embedding=embedding,
            supersedes_id=data.supersedes_id,
            is_fictitious=data.is_fictitious,
        )
        db.add(learning)
        await db.flush()

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="learning_created",
            entity_type="learning",
            entity_id=str(learning.id),
            payload={
                "status": "provisional",
                "source_experiment_id": str(data.source_experiment_id) if data.source_experiment_id else None,
                "confidence": data.confidence,
            },
            result="success",
        )
        db.add(log)
        await db.commit()
        await db.refresh(learning)
        return learning

    async def confirm(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        learning_id: uuid.UUID,
        comment: str | None = None,
    ) -> Learning:
        learning = await self._get(db, org_id, learning_id)
        if not learning:
            raise ValueError("Learning not found.")
        if learning.status != "provisional":
            raise ValueError(f"Cannot confirm learning in status '{learning.status}'.")

        learning.status = "confirmed"
        learning.reviewed_at = datetime.now(UTC)
        learning.reviewed_by_id = actor_id
        learning.review_comment = comment
        learning.responsible_type = "user"

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="learning_confirmed",
            entity_type="learning",
            entity_id=str(learning_id),
            payload={"comment": comment},
            result="success",
        )
        db.add(log)
        await db.commit()
        await db.refresh(learning)
        return learning

    async def reject(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        learning_id: uuid.UUID,
        comment: str,
    ) -> Learning:
        learning = await self._get(db, org_id, learning_id)
        if not learning:
            raise ValueError("Learning not found.")
        if learning.status != "provisional":
            raise ValueError(f"Cannot reject learning in status '{learning.status}'.")

        learning.status = "rejected"
        learning.reviewed_at = datetime.now(UTC)
        learning.reviewed_by_id = actor_id
        learning.review_comment = comment
        learning.responsible_type = "user"

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="learning_rejected",
            entity_type="learning",
            entity_id=str(learning_id),
            payload={"comment": comment},
            result="success",
        )
        db.add(log)
        await db.commit()
        await db.refresh(learning)
        return learning

    async def get(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        learning_id: uuid.UUID,
    ) -> Learning | None:
        return await self._get(db, org_id, learning_id)

    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        status: str | None = None,
        product_id: uuid.UUID | None = None,
        segment: str | None = None,
        objective: str | None = None,
        placement: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Learning], int]:
        from sqlalchemy import func
        q = select(Learning).where(Learning.organization_id == org_id)
        if status:
            q = q.where(Learning.status == status)
        if product_id:
            q = q.where(Learning.product_id == product_id)
        if segment:
            q = q.where(Learning.segment == segment)
        if objective:
            q = q.where(Learning.objective == objective)
        if placement:
            q = q.where(Learning.placement == placement)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar_one()
        q = q.order_by(Learning.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await db.execute(q)).scalars().all()
        return list(rows), total

    async def _get(self, db: AsyncSession, org_id: uuid.UUID, learning_id: uuid.UUID) -> Learning | None:
        result = await db.execute(
            select(Learning).where(Learning.id == learning_id, Learning.organization_id == org_id)
        )
        return result.scalar_one_or_none()


def _mock_embedding(text: str) -> list[float]:
    """Deterministic mock embedding (128-d) for dev/test — no external call."""
    import hashlib
    digest = hashlib.sha256(text.encode()).digest()
    floats = [(b / 127.5) - 1.0 for b in digest]
    # Pad/repeat to 128 dims
    while len(floats) < 128:
        floats.extend(floats[:128 - len(floats)])
    floats = floats[:128]
    # Normalize
    norm = sum(f ** 2 for f in floats) ** 0.5 or 1.0
    return [f / norm for f in floats]
