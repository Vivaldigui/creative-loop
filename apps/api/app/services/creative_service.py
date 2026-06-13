"""
Creative generation pipeline (Phase 4).

Orchestrates: provider → storage → dedup → derivatives → quality + policy gates → status.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.checks import PolicyCheck, QualityCheck
from app.models.creative import GeneratedCreative
from app.models.creative_asset import CreativeAsset
from app.models.prompt import PromptVersion

logger = structlog.get_logger()

# Valid ad formats → (w, h)
FORMAT_MAP: dict[str, tuple[int, int]] = {
    "1080x1080": (1080, 1080),
    "1080x1350": (1080, 1350),
    "1080x1920": (1080, 1920),
    "1200x628": (1200, 628),
}


def _format_label(w: int, h: int) -> str:
    return f"{w}x{h}"


class CreativeService:
    def __init__(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        *,
        image_provider: str = "mock",
        storage_backend: str = "local",
        storage_dir: str = "./storage",
        secret_key: str = "",
        s3_endpoint: str = "",
        s3_bucket: str = "",
        s3_access_key: str = "",
        s3_secret_key: str = "",
        s3_region: str = "auto",
        openai_api_key: str = "",
        openai_model: str = "gpt-image-2",
        openai_timeout_s: float = 90.0,
        openai_max_retries: int = 3,
        similarity_threshold: int = 6,
        max_file_mb: float = 15.0,
        thumbnail_max_px: int = 512,
        cv_enabled: bool = True,
    ) -> None:
        self._db = db
        self._org_id = org_id
        self._actor_id = actor_id
        self._image_provider = image_provider
        self._storage_backend = storage_backend
        self._storage_dir = storage_dir
        self._secret_key = secret_key
        self._s3_endpoint = s3_endpoint
        self._s3_bucket = s3_bucket
        self._s3_access_key = s3_access_key
        self._s3_secret_key = s3_secret_key
        self._s3_region = s3_region
        self._openai_api_key = openai_api_key
        self._openai_model = openai_model
        self._openai_timeout_s = openai_timeout_s
        self._openai_max_retries = openai_max_retries
        self._similarity_threshold = similarity_threshold
        self._max_file_mb = max_file_mb
        self._thumbnail_max_px = thumbnail_max_px
        self._cv_enabled = cv_enabled

    # ── Public API ────────────────────────────────────────────────

    async def generate(
        self,
        *,
        prompt_version_id: uuid.UUID,
        base_width: int = 1080,
        base_height: int = 1080,
        quality: str = "standard",
        n: int = 1,
        extra_formats: list[str] | None = None,
        source_ad_id: uuid.UUID | None = None,
    ) -> list[GeneratedCreative]:
        """
        Full generation pipeline for n variations of a creative.

        Returns a list of GeneratedCreative records (one per variation).
        Each record will have status=awaiting_approval or blocked.
        """
        from packages.openai_image_client.factory import get_image_client
        from packages.openai_image_client.interface import ImageRequest

        # 1. Load PromptVersion (org-scoped)
        pv_result = await self._db.execute(
            select(PromptVersion).where(
                PromptVersion.id == prompt_version_id,
                PromptVersion.organization_id == self._org_id,
            )
        )
        pv = pv_result.scalar_one_or_none()
        if pv is None:
            raise ValueError(f"PromptVersion {prompt_version_id} not found in org {self._org_id}")

        # 2. AuditLog: intent
        await self._audit(
            "generate_creative", "prompt_version", str(prompt_version_id), result="started"
        )

        # 3. Build image request
        image_req = ImageRequest(
            prompt=pv.prompt_text,
            width=base_width,
            height=base_height,
            quality=quality,  # type: ignore[arg-type]
            n=n,
        )

        # 4. Call provider
        provider = get_image_client(
            self._image_provider,
            api_key=self._openai_api_key,
            model=self._openai_model,
            timeout_s=self._openai_timeout_s,
            max_retries=self._openai_max_retries,
        )
        try:
            provider_result = await provider.generate(image_req)
        except Exception as exc:
            logger.error("creative_provider_error", error=str(exc))
            await self._audit(
                "generate_creative", "prompt_version", str(prompt_version_id), result="error"
            )
            raise

        # 5. Process each returned image
        creatives: list[GeneratedCreative] = []
        for img_bytes in provider_result.images:
            creative = await self._process_single_image(
                img_bytes=img_bytes,
                pv=pv,
                provider_result=provider_result,
                base_width=base_width,
                base_height=base_height,
                extra_formats=extra_formats or [],
                source_ad_id=source_ad_id,
            )
            creatives.append(creative)

        # Handle moderation flag at provider level
        if provider_result.moderation_flagged and not creatives:
            creative = await self._create_failed_creative(
                pv=pv,
                provider_result=provider_result,
                reason="Provider flagged content as violating moderation policy.",
                source_ad_id=source_ad_id,
            )
            creatives.append(creative)

        await self._audit(
            "generate_creative",
            "prompt_version",
            str(prompt_version_id),
            result="success",
            payload={"n_generated": len(creatives)},
        )
        return creatives

    # ── Internals ─────────────────────────────────────────────────

    async def _process_single_image(
        self,
        *,
        img_bytes: bytes,
        pv: PromptVersion,
        provider_result: Any,
        base_width: int,
        base_height: int,
        extra_formats: list[str],
        source_ad_id: uuid.UUID | None,
    ) -> GeneratedCreative:
        from packages.storage.factory import get_storage
        from packages.storage.paths import make_key

        from app.services.dedup import (
            compute_phash,
            compute_sha256,
            find_duplicate_hash,
            find_similar_phash,
        )
        from app.services.derivative_service import (
            make_derivative,
            make_thumbnail,
            validate_file_size,
        )

        storage = get_storage(
            self._storage_backend,
            base_dir=self._storage_dir,
            secret_key=self._secret_key,
            s3_endpoint=self._s3_endpoint,
            s3_bucket=self._s3_bucket,
            s3_access_key=self._s3_access_key,
            s3_secret_key=self._s3_secret_key,
            s3_region=self._s3_region,
        )

        # ── a. Hashes ─────────────────────────────────────────────
        sha256 = compute_sha256(img_bytes)
        try:
            phash_str = compute_phash(img_bytes)
        except Exception:
            phash_str = None

        # ── b. File size guard ────────────────────────────────────
        extra_findings_for_qe: list[Any] = []
        if not validate_file_size(img_bytes, self._max_file_mb):
            from packages.quality_engine.engine import QualityFinding

            extra_findings_for_qe.append(
                QualityFinding(
                    check="file_size_exceeded",
                    severity="blocked",
                    detail=f"Image exceeds max {self._max_file_mb} MB after generation.",
                )
            )

        # ── c. Dedup checks ───────────────────────────────────────
        dup_asset_id = await find_duplicate_hash(self._db, self._org_id, sha256)
        if dup_asset_id:
            from packages.quality_engine.engine import QualityFinding

            extra_findings_for_qe.append(
                QualityFinding(
                    check="hash_duplicate",
                    severity="blocked",
                    detail=f"Identical image already exists (asset {dup_asset_id}). No file stored.",
                )
            )

        similar_creative_id: uuid.UUID | None = None
        if not dup_asset_id and phash_str:
            similar_creative_id = await find_similar_phash(
                self._db,
                self._org_id,
                phash_str,
                threshold=self._similarity_threshold,
            )
            if similar_creative_id:
                from packages.quality_engine.engine import QualityFinding

                extra_findings_for_qe.append(
                    QualityFinding(
                        check="too_similar",
                        severity="warning",
                        detail=f"Image is visually similar to creative {similar_creative_id} "
                        f"(pHash distance ≤ {self._similarity_threshold}).",
                    )
                )

        # ── d. Store original (skip if exact duplicate) ───────────
        org_str = str(self._org_id)
        if dup_asset_id:
            storage_key = None
            storage_backend = None
            file_path = None
        else:
            ext = ".png"
            key = make_key(org_str, ext)
            stored = await storage.put(org_str, key, img_bytes, "image/png")
            storage_key = stored.key
            storage_backend = stored.backend
            file_path = storage.local_path(org_str, key)

        # ── e. Create GeneratedCreative record ────────────────────
        creative = GeneratedCreative(
            organization_id=self._org_id,
            prompt_version_id=pv.id,
            provider=provider_result.provider,
            model_used=provider_result.model_used,
            file_path=file_path,
            file_hash=sha256,
            phash=phash_str,
            storage_key=storage_key,
            storage_backend=storage_backend,
            width=base_width,
            height=base_height,
            file_size_bytes=len(img_bytes),
            mime_type=provider_result.mime_type,
            estimated_cost_usd=provider_result.estimated_cost_usd,
            parameters=provider_result.parameters,
            source_ad_id=source_ad_id,
            is_fictitious=pv.is_fictitious,
            status="generated",
        )
        self._db.add(creative)
        await self._db.flush()  # get creative.id

        # ── f. Original asset record ──────────────────────────────
        if not dup_asset_id and storage_key:
            orig_label = _format_label(base_width, base_height)
            orig_asset = CreativeAsset(
                organization_id=self._org_id,
                creative_id=creative.id,
                role="original",
                format_label=orig_label,
                storage_key=storage_key,
                storage_backend=storage_backend or "local",
                width=base_width,
                height=base_height,
                file_size_bytes=len(img_bytes),
                mime_type="image/png",
                file_hash=sha256,
                fit_strategy="none",
                is_fictitious=pv.is_fictitious,
            )
            self._db.add(orig_asset)

            # ── g. Derivatives ────────────────────────────────────
            for fmt in extra_formats:
                if fmt not in FORMAT_MAP:
                    continue
                tw, th = FORMAT_MAP[fmt]
                if (tw, th) == (base_width, base_height):
                    continue  # already stored as original
                try:
                    deriv = make_derivative(img_bytes, tw, th, fmt)
                    deriv_key = make_key(org_str, ".png")
                    deriv_stored = await storage.put(org_str, deriv_key, deriv.data, "image/png")
                    deriv_asset = CreativeAsset(
                        organization_id=self._org_id,
                        creative_id=creative.id,
                        role="derivative",
                        format_label=fmt,
                        storage_key=deriv_stored.key,
                        storage_backend=deriv_stored.backend,
                        width=deriv.width,
                        height=deriv.height,
                        file_size_bytes=deriv.file_size_bytes,
                        mime_type="image/png",
                        file_hash=compute_sha256(deriv.data),
                        fit_strategy=deriv.fit_strategy,
                        is_fictitious=pv.is_fictitious,
                    )
                    self._db.add(deriv_asset)
                except Exception as exc:
                    logger.warning("derivative_failed", fmt=fmt, error=str(exc))

            # ── h. Thumbnail ──────────────────────────────────────
            try:
                thumb = make_thumbnail(img_bytes, max_px=self._thumbnail_max_px)
                thumb_key = make_key(org_str, ".png")
                thumb_stored = await storage.put(org_str, thumb_key, thumb.data, "image/png")
                thumb_asset = CreativeAsset(
                    organization_id=self._org_id,
                    creative_id=creative.id,
                    role="thumbnail",
                    format_label="thumb",
                    storage_key=thumb_stored.key,
                    storage_backend=thumb_stored.backend,
                    width=thumb.width,
                    height=thumb.height,
                    file_size_bytes=thumb.file_size_bytes,
                    mime_type="image/png",
                    file_hash=compute_sha256(thumb.data),
                    fit_strategy=thumb.fit_strategy,
                    is_fictitious=pv.is_fictitious,
                )
                self._db.add(thumb_asset)
            except Exception as exc:
                logger.warning("thumbnail_failed", error=str(exc))

        # ── i. Quality Gate ───────────────────────────────────────
        creative.status = "checking"
        from packages.quality_engine.engine import QualityEngine

        qe = QualityEngine(cv_enabled=self._cv_enabled)
        q_result = qe.check(
            data=img_bytes,
            width=base_width,
            height=base_height,
            prompt_text=pv.prompt_text,
            extra_findings=extra_findings_for_qe,
        )
        qc = QualityCheck(
            organization_id=self._org_id,
            creative_id=creative.id,
            result=q_result.result,
            findings={"findings": [f.model_dump() for f in q_result.findings]},
        )
        self._db.add(qc)

        # ── j. Policy Gate ────────────────────────────────────────
        from packages.policy_engine.engine import PolicyEngine

        pe = PolicyEngine()
        p_result = pe.check(text=pv.prompt_text or "")
        # If provider flagged moderation, inject into policy
        if provider_result.moderation_flagged:
            from packages.policy_engine.engine import PolicyFinding

            p_result.findings.insert(
                0,
                PolicyFinding(
                    rule="moderation_flagged",
                    severity="blocked",
                    detail="Image provider flagged this request as violating content policy.",
                ),
            )
            if p_result.result != "BLOCKED":
                p_result.result = "BLOCKED"

        pc = PolicyCheck(
            organization_id=self._org_id,
            creative_id=creative.id,
            result=p_result.result,
            findings={"findings": [f.model_dump() for f in p_result.findings]},
            rule_set_version=p_result.rule_set_version,
        )
        self._db.add(pc)

        # ── k. Final status ───────────────────────────────────────
        if q_result.result == "BLOCKED" or p_result.result == "BLOCKED":
            creative.status = "blocked"
        else:
            creative.status = "awaiting_approval"

        await self._db.commit()
        await self._db.refresh(creative)
        return creative

    async def _create_failed_creative(
        self,
        *,
        pv: PromptVersion,
        provider_result: Any,
        reason: str,
        source_ad_id: uuid.UUID | None,
    ) -> GeneratedCreative:
        creative = GeneratedCreative(
            organization_id=self._org_id,
            prompt_version_id=pv.id,
            provider=provider_result.provider,
            model_used=provider_result.model_used,
            source_ad_id=source_ad_id,
            is_fictitious=pv.is_fictitious,
            status="blocked",
            parameters={"failure_reason": reason},
        )
        self._db.add(creative)

        from packages.policy_engine.engine import PolicyFinding, PolicyResult

        from app.models.checks import PolicyCheck

        pe_result = PolicyResult(
            result="BLOCKED",
            findings=[PolicyFinding(rule="moderation_flagged", severity="blocked", detail=reason)],
        )
        pc = PolicyCheck(
            organization_id=self._org_id,
            creative_id=creative.id,  # type: ignore[attr-defined]
            result=pe_result.result,
            findings={"findings": [f.model_dump() for f in pe_result.findings]},
        )
        self._db.add(pc)
        await self._db.commit()
        await self._db.refresh(creative)
        return creative

    async def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        *,
        result: str = "success",
        payload: dict | None = None,
    ) -> None:
        audit = AuditLog(
            organization_id=self._org_id,
            actor_id=self._actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            result=result,
            dry_run=False,
        )
        self._db.add(audit)
        await self._db.flush()
