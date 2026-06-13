"""
Prompt service (Phase 3).

Handles:
- generate: create PromptTemplate + PromptVersion v1 (optionally from a hypothesis)
- revise:   create new PromptVersion from an existing template (never overwrites)
- diff:     unified diff + field-level diff between two versions of the same template
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.hypothesis import CreativeHypothesis
from app.models.prompt import PromptTemplate, PromptVersion

logger = structlog.get_logger()


class PromptService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID | None) -> None:
        self._db = db
        self._org_id = org_id
        self._actor_id = actor_id

    # ── Generate ─────────────────────────────────────────────────

    async def generate(
        self,
        *,
        fields: dict[str, Any],
        ad_format: str = "feed",
        objective: str | None = None,
        template_name: str | None = None,
        source_ad_id: uuid.UUID | None = None,
        analysis_id: uuid.UUID | None = None,
        product_id: uuid.UUID | None = None,
        hypothesis_id: uuid.UUID | None = None,
        # If provided, a new CreativeHypothesis is created before the template
        hypothesis_payload: dict[str, Any] | None = None,
        author_type: str = "human",
        target_model: str | None = None,
        generation_parameters: dict[str, Any] | None = None,
    ) -> PromptVersion:
        from packages.prompt_engine.engine import PromptEngine, PromptFields

        # If raw hypothesis payload given, create the entity first
        if hypothesis_payload and not hypothesis_id:
            hyp = await self._create_hypothesis(
                source_ad_id=hypothesis_payload.get("source_ad_id") or source_ad_id,
                analysis_id=hypothesis_payload.get("analysis_id") or analysis_id,
                statement=hypothesis_payload["statement"],
                rationale=hypothesis_payload.get("rationale"),
                primary_variable=hypothesis_payload.get("primary_variable"),
                expected_effect=hypothesis_payload.get("expected_effect"),
                confidence=hypothesis_payload.get("confidence"),
            )
            hypothesis_id = hyp.id

        fields_data = dict(fields)
        fields_data["ad_format"] = ad_format
        if objective:
            fields_data["objective"] = objective
        fields_data.setdefault("originality_note", "This is an original creative. Do not copy any third-party ad.")

        engine = PromptEngine()
        prompt_fields = PromptFields(**{k: v for k, v in fields_data.items() if k in PromptFields.model_fields})
        versioned = engine.new_version(
            prompt_fields, parent_text=None, parent_version=0, change_reason="initial generation"
        )

        template = PromptTemplate(
            organization_id=self._org_id,
            name=template_name or f"Template for {ad_format}",
            product_id=product_id,
            hypothesis_id=hypothesis_id,
            ad_format=ad_format,
            objective=objective,
        )
        self._db.add(template)
        await self._db.flush()

        pv = PromptVersion(
            organization_id=self._org_id,
            template_id=template.id,
            source_ad_id=source_ad_id,
            analysis_id=analysis_id,
            version_number=1,
            prompt_text=versioned.prompt_text,
            structured_fields=versioned.structured_fields,
            content_hash=versioned.content_hash,
            diff_summary=None,
            change_reason="initial generation",
            author_id=self._actor_id,
            author_type=author_type,
            target_model=target_model,
            generation_parameters=generation_parameters,
        )
        self._db.add(pv)

        self._db.add(AuditLog(
            organization_id=self._org_id,
            actor_id=self._actor_id,
            action="generate_prompt",
            entity_type="prompt_template",
            entity_id=str(template.id),
            result="success",
            dry_run=False,
        ))
        await self._db.commit()
        await self._db.refresh(pv)
        return pv

    # ── Revise ────────────────────────────────────────────────────

    async def revise(
        self,
        template_id: uuid.UUID,
        *,
        fields: dict[str, Any],
        change_reason: str,
        base_version_id: uuid.UUID | None = None,
        author_type: str = "human",
        target_model: str | None = None,
        generation_parameters: dict[str, Any] | None = None,
    ) -> PromptVersion:
        from packages.prompt_engine.engine import PromptEngine, PromptFields

        # Verify template belongs to org
        tmpl_result = await self._db.execute(
            select(PromptTemplate).where(
                PromptTemplate.id == template_id,
                PromptTemplate.organization_id == self._org_id,
            )
        )
        template = tmpl_result.scalar_one_or_none()
        if template is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Prompt template not found")

        # Resolve base version
        if base_version_id:
            bv_result = await self._db.execute(
                select(PromptVersion).where(
                    PromptVersion.id == base_version_id,
                    PromptVersion.template_id == template_id,
                    PromptVersion.organization_id == self._org_id,
                )
            )
            parent = bv_result.scalar_one_or_none()
            if parent is None:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Base version not found")
        else:
            # Use latest version
            latest_result = await self._db.execute(
                select(PromptVersion)
                .where(
                    PromptVersion.template_id == template_id,
                    PromptVersion.organization_id == self._org_id,
                )
                .order_by(PromptVersion.version_number.desc())
                .limit(1)
            )
            parent = latest_result.scalar_one_or_none()
            if parent is None:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="No versions found for template")

        engine = PromptEngine()
        merged = {**(parent.structured_fields or {}), **fields}
        prompt_fields = PromptFields(**{k: v for k, v in merged.items() if k in PromptFields.model_fields})

        # Next version number
        max_result = await self._db.execute(
            select(func.max(PromptVersion.version_number)).where(
                PromptVersion.template_id == template_id,
                PromptVersion.organization_id == self._org_id,
            )
        )
        next_num = (max_result.scalar_one_or_none() or 0) + 1

        versioned = engine.new_version(
            prompt_fields,
            parent_text=parent.prompt_text,
            parent_version=next_num - 1,
            change_reason=change_reason,
        )

        # Reject identical revision
        if versioned.content_hash == parent.content_hash:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Revision produces no change — prompt text is identical to parent version.")

        new_pv = PromptVersion(
            organization_id=self._org_id,
            template_id=template_id,
            source_ad_id=parent.source_ad_id,
            analysis_id=parent.analysis_id,
            parent_version_id=parent.id,
            version_number=next_num,
            prompt_text=versioned.prompt_text,
            structured_fields=versioned.structured_fields,
            content_hash=versioned.content_hash,
            diff_summary=versioned.diff_summary,
            change_reason=change_reason,
            author_id=self._actor_id,
            author_type=author_type,
            target_model=target_model or parent.target_model,
            generation_parameters=generation_parameters or parent.generation_parameters,
        )
        self._db.add(new_pv)

        self._db.add(AuditLog(
            organization_id=self._org_id,
            actor_id=self._actor_id,
            action="revise_prompt",
            entity_type="prompt_template",
            entity_id=str(template_id),
            payload={"base_version": str(parent.id), "new_version_number": next_num},
            result="success",
            dry_run=False,
        ))
        await self._db.commit()
        await self._db.refresh(new_pv)
        return new_pv

    # ── Diff ─────────────────────────────────────────────────────

    async def diff(
        self, version_a_id: uuid.UUID, version_b_id: uuid.UUID
    ) -> dict[str, Any]:
        """Return unified diff + field-level diff between two versions (must share template and org)."""
        from packages.prompt_engine.engine import PromptEngine

        va, vb = await self._load_two_versions(version_a_id, version_b_id)

        engine = PromptEngine()
        unified = engine.diff(va.prompt_text, vb.prompt_text)

        fields_a = va.structured_fields or {}
        fields_b = vb.structured_fields or {}
        all_keys = set(fields_a) | set(fields_b)
        field_diff: dict[str, Any] = {}
        for key in sorted(all_keys):
            old_val = fields_a.get(key)
            new_val = fields_b.get(key)
            if old_val != new_val:
                field_diff[key] = {"from": old_val, "to": new_val}

        return {
            "version_a": {"id": str(va.id), "version_number": va.version_number},
            "version_b": {"id": str(vb.id), "version_number": vb.version_number},
            "unified_diff": unified,
            "field_changes": field_diff,
            "changed_field_count": len(field_diff),
        }

    # ── Helpers ───────────────────────────────────────────────────

    async def _load_two_versions(
        self, a_id: uuid.UUID, b_id: uuid.UUID
    ) -> tuple[PromptVersion, PromptVersion]:
        from fastapi import HTTPException

        ra = await self._db.execute(
            select(PromptVersion).where(
                PromptVersion.id == a_id,
                PromptVersion.organization_id == self._org_id,
            )
        )
        va = ra.scalar_one_or_none()
        rb = await self._db.execute(
            select(PromptVersion).where(
                PromptVersion.id == b_id,
                PromptVersion.organization_id == self._org_id,
            )
        )
        vb = rb.scalar_one_or_none()

        if va is None or vb is None:
            raise HTTPException(status_code=404, detail="One or both versions not found")
        if va.template_id != vb.template_id:
            raise HTTPException(
                status_code=422,
                detail="Cannot diff versions from different templates",
            )
        return va, vb

    async def _create_hypothesis(
        self,
        *,
        source_ad_id: uuid.UUID | None,
        analysis_id: uuid.UUID | None,
        statement: str,
        rationale: str | None,
        primary_variable: str | None,
        expected_effect: str | None,
        confidence: float | None,
    ) -> CreativeHypothesis:
        from fastapi import HTTPException

        if not source_ad_id or not analysis_id:
            raise HTTPException(
                status_code=422,
                detail="hypothesis_payload requires source_ad_id and analysis_id",
            )
        hyp = CreativeHypothesis(
            organization_id=self._org_id,
            source_ad_id=source_ad_id,
            analysis_id=analysis_id,
            statement=statement,
            rationale=rationale,
            primary_variable=primary_variable,
            expected_effect=expected_effect,
            confidence=confidence,
            status="selected",
        )
        self._db.add(hyp)
        await self._db.flush()
        return hyp
