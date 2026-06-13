"""
NextRoundService — suggests next experiment round.

Safety contract (v1):
- NEVER generates images automatically.
- NEVER publishes automatically.
- Creates ONLY draft experiment + draft prompt version.
- Requires human approval before any downstream generation/publication.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models.audit import AuditLog
from app.models.evaluation import ExperimentEvaluation
from app.models.experiment import Experiment
from app.models.learning import Learning, LearningUsage
from app.models.prompt import PromptTemplate, PromptVersion
from app.models.suggestion import ExperimentSuggestion
from app.services.retrieval_service import LearningRetrievalService

logger = structlog.get_logger()


class NextRoundService:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._retrieval = LearningRetrievalService(settings)

    async def suggest(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> ExperimentSuggestion:
        """
        Create a next-round suggestion:
        1. Load source experiment + latest evaluation.
        2. Retrieve relevant learnings.
        3. Formulate hypothesis.
        4. Create draft Experiment + draft PromptVersion.
        5. Compute diversity score.
        6. Create ExperimentSuggestion (status=pending_approval).
        NO image generation, NO publish.
        """
        # Check for existing pending suggestion to avoid duplicates
        existing = await db.execute(
            select(ExperimentSuggestion).where(
                ExperimentSuggestion.source_experiment_id == experiment_id,
                ExperimentSuggestion.organization_id == org_id,
                ExperimentSuggestion.status == "pending_approval",
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            raise ValueError("A pending suggestion already exists for this experiment. Approve or reject it first.")

        # Load source experiment
        exp_result = await db.execute(
            select(Experiment)
            .where(Experiment.id == experiment_id, Experiment.organization_id == org_id)
            .options(selectinload(Experiment.variants))
        )
        exp = exp_result.scalar_one_or_none()
        if not exp:
            raise ValueError("Experiment not found.")

        # Load latest evaluation
        eval_result = await db.execute(
            select(ExperimentEvaluation)
            .where(
                ExperimentEvaluation.experiment_id == experiment_id,
                ExperimentEvaluation.organization_id == org_id,
            )
            .order_by(ExperimentEvaluation.evaluated_at.desc())
            .limit(1)
        )
        latest_eval = eval_result.scalar_one_or_none()

        if not latest_eval or latest_eval.evaluation_state in ("insufficient_data", "collecting"):
            raise ValueError("Insufficient evaluation data to suggest a next round.")

        # Retrieve relevant learnings
        relevant_learnings = await self._retrieval.query(
            db=db,
            org_id=org_id,
            product_id=exp.product_id,
            segment=None,
            objective=exp.objective,
            placement=exp.placement,
            reference_text=exp.hypothesis or exp.name,
            max_results=self._settings.exp_retrieval_max_results,
        )
        learning_ids = [str(lr.id) for lr in relevant_learnings]

        # Formulate hypothesis from evaluation + learnings
        hypothesis, primary_variable, rationale = _formulate_hypothesis(exp, latest_eval, relevant_learnings)

        # Create draft Experiment (status=draft, is_fictitious=False)
        draft_exp = Experiment(
            organization_id=org_id,
            name=f"[Draft] Next round: {exp.name}",
            mode="CONTROLLED",
            hypothesis=hypothesis,
            primary_variable=primary_variable,
            status="draft",
            objective=exp.objective,
            product_id=exp.product_id,
            audience=exp.audience,
            placement=exp.placement,
            primary_metric=exp.primary_metric,
            secondary_metrics=exp.secondary_metrics,
            min_criteria=exp.min_criteria,
            currency=exp.currency,
        )
        db.add(draft_exp)
        await db.flush()

        # Create draft PromptVersion based on winning variant's prompt (if any)
        draft_pv_id = await _create_draft_prompt(db, org_id, exp, latest_eval, hypothesis, rationale)

        # Compute diversity score
        diversity = await self._retrieval.compute_diversity_score(
            db=db,
            org_id=org_id,
            candidate_prompt_hash=None,
            candidate_phash=None,
            variation_depth=0,
            selected_learning_ids=learning_ids,
        )

        # Create suggestion
        suggestion = ExperimentSuggestion(
            organization_id=org_id,
            source_experiment_id=experiment_id,
            draft_experiment_id=draft_exp.id,
            draft_prompt_version_id=draft_pv_id,
            selected_learning_ids=learning_ids,
            hypothesis=hypothesis,
            primary_variable=primary_variable,
            rationale=rationale,
            diversity_score=diversity,
            status="pending_approval",
            context_snapshot={
                "evaluation_state": latest_eval.evaluation_state,
                "confidence": latest_eval.confidence,
                "primary_metric": exp.primary_metric,
                "source_experiment_name": exp.name,
                "learnings_count": len(relevant_learnings),
            },
        )
        db.add(suggestion)
        await db.flush()

        # Record learning usage
        for lid in learning_ids:
            try:
                usage = LearningUsage(
                    organization_id=org_id,
                    learning_id=uuid.UUID(lid),
                    suggestion_id=suggestion.id,
                    prompt_version_id=draft_pv_id,
                    used_at=datetime.now(UTC),
                )
                db.add(usage)
            except ValueError:
                pass

        # AuditLog — intent
        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="next_round_suggested",
            entity_type="experiment_suggestion",
            entity_id=str(suggestion.id),
            payload={
                "source_experiment_id": str(experiment_id),
                "evaluation_state": latest_eval.evaluation_state,
                "learnings_used": len(learning_ids),
                "diversity_score": diversity,
                "auto_image_generation": False,
                "auto_publish": False,
            },
            result="success",
        )
        db.add(log)
        suggestion.audit_log_id = log.id
        await db.commit()
        await db.refresh(suggestion)
        return suggestion

    async def approve(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        suggestion_id: uuid.UUID,
        comment: str | None = None,
    ) -> ExperimentSuggestion:
        suggestion = await self._get(db, org_id, suggestion_id)
        if not suggestion:
            raise ValueError("Suggestion not found.")
        if suggestion.status != "pending_approval":
            raise ValueError(f"Cannot approve suggestion in status '{suggestion.status}'.")

        suggestion.status = "approved"
        suggestion.reviewed_by_id = actor_id
        suggestion.reviewed_at = datetime.now(UTC)
        suggestion.review_comment = comment

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="suggestion_approved",
            entity_type="experiment_suggestion",
            entity_id=str(suggestion_id),
            payload={"comment": comment, "auto_image_generation": False, "auto_publish": False},
            result="success",
        )
        db.add(log)
        await db.commit()
        await db.refresh(suggestion)
        return suggestion

    async def reject(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID,
        suggestion_id: uuid.UUID,
        comment: str | None = None,
    ) -> ExperimentSuggestion:
        suggestion = await self._get(db, org_id, suggestion_id)
        if not suggestion:
            raise ValueError("Suggestion not found.")
        if suggestion.status != "pending_approval":
            raise ValueError(f"Cannot reject suggestion in status '{suggestion.status}'.")

        suggestion.status = "rejected"
        suggestion.reviewed_by_id = actor_id
        suggestion.reviewed_at = datetime.now(UTC)
        suggestion.review_comment = comment

        log = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action="suggestion_rejected",
            entity_type="experiment_suggestion",
            entity_id=str(suggestion_id),
            payload={"comment": comment},
            result="success",
        )
        db.add(log)
        await db.commit()
        await db.refresh(suggestion)
        return suggestion

    async def get(self, db: AsyncSession, org_id: uuid.UUID, suggestion_id: uuid.UUID) -> ExperimentSuggestion | None:
        return await self._get(db, org_id, suggestion_id)

    async def list_for_experiment(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> list[ExperimentSuggestion]:
        result = await db.execute(
            select(ExperimentSuggestion).where(
                ExperimentSuggestion.source_experiment_id == experiment_id,
                ExperimentSuggestion.organization_id == org_id,
            ).order_by(ExperimentSuggestion.created_at.desc())
        )
        return list(result.scalars().all())

    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        status: str | None = None,
    ) -> list[ExperimentSuggestion]:
        q = select(ExperimentSuggestion).where(ExperimentSuggestion.organization_id == org_id)
        if status:
            q = q.where(ExperimentSuggestion.status == status)
        q = q.order_by(ExperimentSuggestion.created_at.desc())
        result = await db.execute(q)
        return list(result.scalars().all())

    async def _get(self, db: AsyncSession, org_id: uuid.UUID, suggestion_id: uuid.UUID) -> ExperimentSuggestion | None:
        result = await db.execute(
            select(ExperimentSuggestion).where(
                ExperimentSuggestion.id == suggestion_id,
                ExperimentSuggestion.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _formulate_hypothesis(
    exp: Experiment,
    evaluation: ExperimentEvaluation,
    learnings: list[Learning],
) -> tuple[str, str | None, str]:
    state = evaluation.evaluation_state
    primary_var = exp.primary_variable

    # Build rationale from learnings
    patterns = [f"- {lr.observed_pattern[:120]}" for lr in learnings[:3]]
    rationale_parts = [
        f"Source experiment '{exp.name}' ended with evaluation state: {state}.",
        f"Confidence: {evaluation.confidence:.2f}." if evaluation.confidence else "",
        "Relevant learnings:" if patterns else "",
    ] + patterns

    rationale = " ".join(p for p in rationale_parts if p)

    # Choose next variable to test based on state
    next_var = primary_var
    if state == "winner_candidate" and primary_var:
        # Continue testing same variable with refined hypothesis
        hyp = (
            f"Building on the winner from '{exp.name}', further optimizing {primary_var} "
            f"to confirm and extend the improvement observed."
        )
    elif state in ("promising", "inconclusive"):
        hyp = (
            f"Test a refined {primary_var or 'creative element'} based on learnings from '{exp.name}'. "
            f"Expected: improvement in {exp.primary_metric or 'primary metric'}."
        )
    elif state == "underperforming":
        hyp = (
            f"Test an alternative approach for {primary_var or 'creative'} after '{exp.name}' underperformed. "
            f"Learnings suggest different direction."
        )
    else:
        hyp = (
            f"Exploratory follow-up to '{exp.name}' based on available learnings. "
            f"No strong prior direction — EXPLORATORY mode recommended."
        )
        next_var = None

    return hyp, next_var, rationale


async def _create_draft_prompt(
    db: AsyncSession,
    org_id: uuid.UUID,
    exp: Experiment,
    evaluation: ExperimentEvaluation,
    hypothesis: str,
    rationale: str,
) -> uuid.UUID | None:
    """Create a draft PromptVersion based on existing template or create a new template."""
    # Try to find an existing template for this product
    tmpl_result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.organization_id == org_id,
            PromptTemplate.product_id == exp.product_id if exp.product_id else True,
        ).order_by(PromptTemplate.created_at.desc()).limit(1)
    )
    tmpl = tmpl_result.scalar_one_or_none()

    if not tmpl:
        tmpl = PromptTemplate(
            organization_id=org_id,
            name=f"[Draft] Prompt for next round of '{exp.name}'",
            product_id=exp.product_id,
            status="draft",
        )
        db.add(tmpl)
        await db.flush()

    # Find latest version of this template
    pv_result = await db.execute(
        select(PromptVersion).where(
            PromptVersion.organization_id == org_id,
            PromptVersion.template_id == tmpl.id,
        ).order_by(PromptVersion.version_number.desc()).limit(1)
    )
    parent_pv = pv_result.scalar_one_or_none()

    prompt_text = (
        f"[DRAFT - REQUIRES HUMAN REVIEW]\n\n"
        f"Hypothesis: {hypothesis}\n\n"
        f"Rationale: {rationale}\n\n"
        f"Primary variable to test: {exp.primary_variable or 'TBD'}\n"
        f"Objective: {exp.objective or 'TBD'}\n\n"
        f"[Add specific creative instructions here after review]"
    )

    import hashlib
    content_hash = hashlib.sha256(prompt_text.encode()).hexdigest()

    pv = PromptVersion(
        organization_id=org_id,
        template_id=tmpl.id,
        version_number=(parent_pv.version_number + 1) if parent_pv else 1,
        prompt_text=prompt_text,
        change_reason=f"AI-generated draft for next round of experiment '{exp.name}'",
        author_type="agent",
        content_hash=content_hash,
        parent_version_id=parent_pv.id if parent_pv else None,
        learning_used=rationale[:500] if rationale else None,
    )
    db.add(pv)
    await db.flush()
    return pv.id
