#!/usr/bin/env python3
"""
Seed script — Phase 1 fictitious data.
All records are marked is_fictitious=True and metadata={'fictitious': True}.
Run: python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))  # makes `packages` importable as top-level

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.security.hashing import hash_password  # noqa: E402


async def run_seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        from sqlalchemy import select
        from app.models.user import Organization, User
        from app.models.credential import IntegrationCredential
        from app.models.product import BrandProfile, Product
        from app.models.source_ad import PerformanceSnapshot, SourceAd
        from app.models.analysis import CreativeAnalysis
        from app.models.prompt import PromptTemplate, PromptVersion
        from app.models.creative import GeneratedCreative
        from app.models.checks import PolicyCheck, QualityCheck
        from app.models.approval import Approval
        from app.models.experiment import Experiment, ExperimentVariant

        # ── Org already exists? ──────────────────────────────────
        existing = await db.execute(
            select(Organization).where(Organization.slug == "demo-org")
        )
        org = existing.scalar_one_or_none()
        if org:
            print("[seed] Demo org already exists. Skipping.")
            return

        # ── Organization ─────────────────────────────────────────
        org = Organization(
            name="[FICTITIOUS] Demo Organization",
            slug="demo-org",
            status="active",
            metadata_={"fictitious": True},
        )
        db.add(org)
        await db.flush()
        print(f"[seed] Organization: {org.id}")

        # ── Admin user ───────────────────────────────────────────
        user = User(
            organization_id=org.id,
            email="admin@demo.example",
            hashed_password=hash_password("demo1234"),
            full_name="[FICTITIOUS] Admin Demo",
            role="owner",
            is_active=True,
            metadata_={"fictitious": True},
        )
        db.add(user)
        await db.flush()
        print(f"[seed] User: {user.email}")

        # ── Integration credentials (not_configured) ─────────────
        for provider in ["meta", "anthropic", "openai"]:
            cred = IntegrationCredential(
                organization_id=org.id,
                provider=provider,
                name=f"[FICTITIOUS] {provider.title()} Integration",
                status="not_configured",
                metadata_={
                    "fictitious": True,
                    "note": f"Set {provider.upper()}_* vars in .env",
                },
            )
            db.add(cred)

        # ── Product ──────────────────────────────────────────────
        product = Product(
            organization_id=org.id,
            name="[FICTITIOUS] SkinGlow Pro",
            description="[FICTITIOUS] Premium skincare serum for all skin types.",
            category="Beauty & Personal Care",
            is_fictitious=True,
            metadata_={"fictitious": True},
        )
        db.add(product)
        await db.flush()
        print(f"[seed] Product: {product.name}")

        # ── Brand Profile ─────────────────────────────────────────
        brand = BrandProfile(
            organization_id=org.id,
            product_id=product.id,
            name="[FICTITIOUS] SkinGlow Brand",
            primary_color="#E8B4C8",
            secondary_color="#FFFFFF",
            font_family="Inter",
            tone_of_voice="[FICTITIOUS] Warm, empowering, science-backed.",
            logo_guidelines="[FICTITIOUS] Logo must appear in top-left corner. Minimum size: 80px.",
            prohibited_elements="[FICTITIOUS] No before/after images. No medical claims.",
            metadata_={"fictitious": True},
        )
        db.add(brand)
        await db.flush()

        # ── 5 Fictitious source ads with metrics ─────────────────
        ads_data = [
            {
                "name": "[FICTITIOUS] Ad A — Product Hero Shot",
                "headline": "[FICTITIOUS] Glow That Lasts All Day",
                "body_text": "[FICTITIOUS] Discover your most radiant skin yet.",
                "cta": "Shop Now",
                "ad_format": "single_image",
                "placement": "feed",
                "objective": "CONVERSIONS",
                "performance_label": "winner",
                "metrics": {
                    "impressions": 50000,
                    "spend": 420.0,
                    "clicks": 1800,
                    "link_clicks": 1500,
                    "ctr": 3.6,
                    "cpc": 0.28,
                    "cpm": 8.4,
                    "purchases": 42,
                    "roas": 3.2,
                    "purchase_value": 1344.0,
                },
            },
            {
                "name": "[FICTITIOUS] Ad B — Lifestyle Scene",
                "headline": "[FICTITIOUS] Feel Confident Every Morning",
                "body_text": "[FICTITIOUS] Used by 50,000+ happy customers.",
                "cta": "Learn More",
                "ad_format": "single_image",
                "placement": "stories",
                "objective": "CONVERSIONS",
                "performance_label": "neutral",
                "metrics": {
                    "impressions": 35000,
                    "spend": 290.0,
                    "clicks": 980,
                    "link_clicks": 820,
                    "ctr": 2.8,
                    "cpc": 0.35,
                    "cpm": 8.3,
                    "purchases": 18,
                    "roas": 1.9,
                    "purchase_value": 551.0,
                },
            },
            {
                "name": "[FICTITIOUS] Ad C — Ingredient Focus",
                "headline": "[FICTITIOUS] 97% Naturally Derived Ingredients",
                "body_text": "[FICTITIOUS] Retinol + Hyaluronic Acid. Visible results in 2 weeks.",
                "cta": "Buy Now",
                "ad_format": "carousel",
                "placement": "feed",
                "objective": "CONVERSIONS",
                "performance_label": "winner",
                "metrics": {
                    "impressions": 62000,
                    "spend": 510.0,
                    "clicks": 2400,
                    "link_clicks": 2100,
                    "ctr": 3.9,
                    "cpc": 0.24,
                    "cpm": 8.2,
                    "purchases": 58,
                    "roas": 3.8,
                    "purchase_value": 1938.0,
                },
            },
            {
                "name": "[FICTITIOUS] Ad D — Text Heavy",
                "headline": "[FICTITIOUS] THE ULTIMATE SKIN SOLUTION — BUY 2 GET 1 FREE TODAY ONLY",
                "body_text": "[FICTITIOUS] Don't miss this exclusive offer. LIMITED TIME.",
                "cta": "Claim Now",
                "ad_format": "single_image",
                "placement": "feed",
                "objective": "CONVERSIONS",
                "performance_label": "loser",
                "metrics": {
                    "impressions": 28000,
                    "spend": 380.0,
                    "clicks": 520,
                    "link_clicks": 350,
                    "ctr": 1.9,
                    "cpc": 1.09,
                    "cpm": 13.6,
                    "purchases": 4,
                    "roas": 0.4,
                    "purchase_value": 152.0,
                },
            },
            {
                "name": "[FICTITIOUS] Ad E — Video Thumbnail",
                "headline": "[FICTITIOUS] Watch Your Skin Transform",
                "body_text": "[FICTITIOUS] See real results from real people.",
                "cta": "Watch Now",
                "ad_format": "video",
                "placement": "reels",
                "objective": "VIDEO_VIEWS",
                "performance_label": "neutral",
                "metrics": {
                    "impressions": 90000,
                    "spend": 180.0,
                    "clicks": 3200,
                    "link_clicks": 1100,
                    "ctr": 3.6,
                    "cpc": 0.16,
                    "cpm": 2.0,
                    "purchases": 8,
                    "roas": 1.4,
                    "purchase_value": 252.0,
                },
            },
        ]

        source_ads = []
        for d in ads_data:
            ad = SourceAd(
                organization_id=org.id,
                product_id=product.id,
                name=d["name"],
                headline=d["headline"],
                body_text=d["body_text"],
                cta=d["cta"],
                ad_format=d["ad_format"],
                placement=d["placement"],
                objective=d["objective"],
                status="active",
                performance_label=d["performance_label"],
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(ad)
            await db.flush()
            source_ads.append(ad)

            m = d["metrics"]
            snap = PerformanceSnapshot(
                organization_id=org.id,
                source_ad_id=ad.id,
                date_start="2025-01-01",
                date_stop="2025-03-31",
                impressions=m["impressions"],
                spend=m["spend"],
                clicks=m["clicks"],
                link_clicks=m["link_clicks"],
                ctr=m["ctr"],
                cpc=m["cpc"],
                cpm=m["cpm"],
                purchases=m["purchases"],
                roas=m["roas"],
                purchase_value=m["purchase_value"],
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(snap)

        print(f"[seed] {len(source_ads)} source ads created")
        await db.flush()

        # ── 3 Analyses (for ads A, B, C) ──────────────────────────
        analyses = []
        for i, ad in enumerate(source_ads[:3]):
            analysis = CreativeAnalysis(
                organization_id=org.id,
                source_ad_id=ad.id,
                provider="mock",
                model_used="mock-deterministic",
                visual_summary=f"[FICTITIOUS MOCK ANALYSIS] Ad '{ad.name}'. This is fictitious seed data.",
                strengths={
                    "items": ["[mock] Clear product shot", "[mock] Strong brand colors"]
                },
                weaknesses={
                    "items": ["[mock] No lifestyle context", "[mock] Generic CTA"]
                },
                performance_hypotheses={
                    "items": [
                        "[mock hypothesis] Adding lifestyle context may improve CTR."
                    ]
                },
                elements_to_test={"items": ["[mock] background", "[mock] CTA text"]},
                confidence=0.5,
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(analysis)
            analyses.append(analysis)
        await db.flush()
        print(f"[seed] {len(analyses)} analyses created")

        # ── 3 PromptTemplates + PromptVersions ────────────────────
        prompt_versions_created = []
        prompts_data = [
            {
                "name": "[FICTITIOUS] Feed 1:1 — Hero Shot v1",
                "fields": {
                    "objective": "Drive conversions",
                    "ad_format": "single_image",
                    "dimensions": "1080x1080",
                    "product_name": "SkinGlow Pro",
                    "brand_name": "SkinGlow",
                    "composition": "Product centered, 60% frame",
                    "background": "Clean white gradient",
                    "cta_text": "Shop Now",
                },
                "text": (
                    "OBJECTIVE: Drive conversions\n"
                    "PRODUCT: SkinGlow Pro\n"
                    "BRAND: SkinGlow\n"
                    "FORMAT: single_image\n"
                    "DIMENSIONS: 1080x1080\n"
                    "COMPOSITION: Product centered, 60% frame\n"
                    "BACKGROUND: Clean white gradient\n"
                    "CTA: Shop Now\n"
                    "NOTE: This is an original creative. Do not copy any third-party ad."
                ),
            },
            {
                "name": "[FICTITIOUS] Stories 9:16 — Lifestyle v1",
                "fields": {
                    "objective": "Brand awareness",
                    "ad_format": "stories",
                    "dimensions": "1080x1920",
                    "product_name": "SkinGlow Pro",
                    "composition": "Lifestyle: person using product",
                    "background": "Natural bathroom setting",
                    "cta_text": "Learn More",
                },
                "text": (
                    "OBJECTIVE: Brand awareness\n"
                    "PRODUCT: SkinGlow Pro\n"
                    "FORMAT: stories\n"
                    "DIMENSIONS: 1080x1920\n"
                    "COMPOSITION: Lifestyle: person using product\n"
                    "BACKGROUND: Natural bathroom setting\n"
                    "CTA: Learn More\n"
                    "NOTE: This is an original creative. Do not copy any third-party ad."
                ),
            },
            {
                "name": "[FICTITIOUS] Feed 4:5 — Ingredient Focus v1",
                "fields": {
                    "objective": "Drive conversions",
                    "ad_format": "single_image",
                    "dimensions": "1080x1350",
                    "product_name": "SkinGlow Pro",
                    "composition": "Ingredient callouts with product",
                    "background": "Soft pink gradient",
                    "headline_text": "97% Natural",
                    "cta_text": "Buy Now",
                },
                "text": (
                    "OBJECTIVE: Drive conversions\n"
                    "PRODUCT: SkinGlow Pro\n"
                    "FORMAT: single_image\n"
                    "DIMENSIONS: 1080x1350\n"
                    "COMPOSITION: Ingredient callouts with product\n"
                    "BACKGROUND: Soft pink gradient\n"
                    "HEADLINE: 97% Natural\n"
                    "CTA: Buy Now\n"
                    "NOTE: This is an original creative. Do not copy any third-party ad."
                ),
            },
        ]

        templates = []
        for i, pd in enumerate(prompts_data):
            tmpl = PromptTemplate(
                organization_id=org.id,
                product_id=product.id,
                name=pd["name"],
                status="active",
                metadata_={"fictitious": True},
            )
            db.add(tmpl)
            await db.flush()
            templates.append(tmpl)

            pv = PromptVersion(
                organization_id=org.id,
                template_id=tmpl.id,
                source_ad_id=source_ads[i].id if i < len(source_ads) else None,
                analysis_id=analyses[i].id if i < len(analyses) else None,
                version_number=1,
                prompt_text=pd["text"],
                structured_fields=pd["fields"],
                change_reason="initial seed",
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(pv)
            prompt_versions_created.append(pv)
        await db.flush()
        print(f"[seed] {len(templates)} prompt templates + versions created")

        # ── 4 GeneratedCreatives (placeholder images) ──────────────
        from packages.openai_image_client.mock import MockImageClient
        from packages.openai_image_client.interface import ImageRequest
        from packages.storage.factory import get_storage
        from packages.storage.paths import make_key
        from app.services.dedup import compute_sha256

        img_client = MockImageClient()
        storage = get_storage(
            settings.storage_backend,
            base_dir=str(ROOT / "storage"),
            secret_key=settings.secret_key,
            s3_endpoint=settings.s3_endpoint,
            s3_bucket=settings.s3_bucket,
            s3_access_key=settings.s3_access_key,
            s3_secret_key=settings.s3_secret_key,
            s3_region=settings.s3_region,
        )
        org_str = str(org.id)

        async def _store_creative(
            pv_id, prompt: str, w: int, h: int, status: str
        ) -> GeneratedCreative:
            result = await img_client.generate(
                ImageRequest(prompt=prompt, width=w, height=h)
            )
            img_bytes = result.images[0]
            sha256 = compute_sha256(img_bytes)
            key = make_key(org_str, ".png")
            stored = await storage.put(org_str, key, img_bytes, "image/png")
            c = GeneratedCreative(
                organization_id=org.id,
                prompt_version_id=pv_id,
                provider="mock",
                model_used="mock-pillow",
                file_path=storage.local_path(org_str, key),
                file_hash=sha256,
                storage_key=stored.key,
                storage_backend=stored.backend,
                width=w,
                height=h,
                file_size_bytes=len(img_bytes),
                mime_type="image/png",
                estimated_cost_usd=0.0,
                status=status,
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(c)
            return c

        dims = [(1080, 1080), (1080, 1080), (1080, 1350)]
        creatives = []
        for i, pv in enumerate(prompt_versions_created[:3]):
            w, h = dims[i]
            creatives.append(
                await _store_creative(
                    pv.id,
                    pv.prompt_text,
                    w,
                    h,
                    status="pending_review" if i < 2 else "approved",
                )
            )
        await db.flush()

        # 4th creative (extra placeholder for approval queue demo)
        extra_creative = await _store_creative(
            prompt_versions_created[0].id,
            "[FICTITIOUS] Extra placeholder creative for approval queue demo",
            1080,
            1080,
            status="pending_review",
        )
        creatives.append(extra_creative)
        await db.flush()
        print(f"[seed] {len(creatives)} generated creatives created")

        # ── Quality + Policy checks for the 3rd creative (approved) ─
        qc = QualityCheck(
            organization_id=org.id,
            creative_id=creatives[2].id,
            result="PASS",
            findings={"findings": []},
        )
        pc = PolicyCheck(
            organization_id=org.id,
            creative_id=creatives[2].id,
            result="PASS",
            findings={"findings": []},
            rule_set_version="1.0.0",
        )
        db.add(qc)
        db.add(pc)

        approval = Approval(
            organization_id=org.id,
            creative_id=creatives[2].id,
            decision="approved",
            decided_by=user.id,
            comment="[FICTITIOUS] Approved for demo purposes.",
            snapshot_prompt=prompt_versions_created[2].prompt_text,
        )
        db.add(approval)

        # ── Quality + Policy for the extra creative (pending_review) ─
        qc2 = QualityCheck(
            organization_id=org.id,
            creative_id=extra_creative.id,
            result="PASS",
            findings={"findings": []},
        )
        pc2 = PolicyCheck(
            organization_id=org.id,
            creative_id=extra_creative.id,
            result="PASS",
            findings={"findings": []},
            rule_set_version="1.0.0",
        )
        db.add(qc2)
        db.add(pc2)

        # ── Phase 7 — Experiment (CONTROLLED, running) ────────────
        from datetime import UTC, date, datetime

        from app.models.variant_metric import VariantPerformanceSnapshot
        from app.models.evaluation import ExperimentEvaluation
        from app.models.decision import OptimizationDecision
        from app.models.learning import Learning, LearningUsage
        from app.models.suggestion import ExperimentSuggestion

        min_criteria = {
            "min_spend": 200.0,
            "min_impressions": 10000,
            "min_clicks": 100,
            "min_days": 7,
            "min_difference": 0.05,
            "min_confidence": 0.75,
            "maturation_window_days": 1,
        }

        experiment = Experiment(
            organization_id=org.id,
            name="[FICTITIOUS] Background Color Test",
            mode="CONTROLLED",
            hypothesis="[FICTITIOUS] A pink gradient background will increase CTR vs white background for this audience.",
            primary_variable="background_color",
            status="running",
            objective="CONVERSIONS",
            product_id=product.id,
            placement="feed",
            window_start=date(2025, 4, 1),
            window_end=date(2025, 4, 30),
            planned_budget=600.0,
            currency=settings.default_currency,
            primary_metric="ctr",
            secondary_metrics=["roas", "cpc"],
            min_criteria=min_criteria,
            evaluation_state="promising",
            started_at=datetime(2025, 4, 1, tzinfo=UTC),
            # legacy mirror (kept for backward compat)
            min_spend=200.0,
            min_impressions=10000,
            min_days=7,
            is_fictitious=True,
            metadata_={"fictitious": True},
        )
        db.add(experiment)
        await db.flush()

        # Control = white BG (lower CTR); Test = pink BG (higher CTR)
        variant_metrics = [
            # (is_control, name, hyp, changed_vars, snapshot)
            (
                True,
                "Control — White BG",
                "Baseline",
                [],
                {
                    "impressions": 14000,
                    "clicks": 420,
                    "link_clicks": 380,
                    "spend": 150.0,
                    "ctr": 3.0,
                    "cpc": 0.36,
                    "cpm": 10.7,
                    "purchases": 14,
                    "roas": 2.6,
                    "purchase_value": 390.0,
                },
            ),
            (
                False,
                "Test — Pink BG",
                "Pink BG drives higher CTR",
                ["background_color"],
                {
                    "impressions": 14500,
                    "clicks": 580,
                    "link_clicks": 520,
                    "spend": 155.0,
                    "ctr": 4.0,
                    "cpc": 0.27,
                    "cpm": 10.7,
                    "purchases": 22,
                    "roas": 3.4,
                    "purchase_value": 527.0,
                },
            ),
        ]

        variants_created: list[ExperimentVariant] = []
        for creative, (is_ctrl, name, hyp, changed, m) in zip(
            creatives[:2], variant_metrics
        ):
            variant = ExperimentVariant(
                organization_id=org.id,
                experiment_id=experiment.id,
                creative_id=creative.id,
                name="[FICTITIOUS] " + name,
                hypothesis="[FICTITIOUS] " + hyp,
                is_control=is_ctrl,
                variant_role="control" if is_ctrl else "test",
                changed_variables=changed,
                allocated_budget=300.0,
                status="running",
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(variant)
            await db.flush()
            variants_created.append(variant)

            snap = VariantPerformanceSnapshot(
                organization_id=org.id,
                experiment_id=experiment.id,
                variant_id=variant.id,
                date_start="2025-04-01",
                date_stop="2025-04-14",
                impressions=m["impressions"],
                clicks=m["clicks"],
                link_clicks=m["link_clicks"],
                spend=m["spend"],
                ctr=m["ctr"],
                cpc=m["cpc"],
                cpm=m["cpm"],
                purchases=m["purchases"],
                roas=m["roas"],
                purchase_value=m["purchase_value"],
                level="ad",
                attribution_window="7d_click",
                currency=settings.default_currency,
                normalization_version="1.0.0",
                roas_source="reported",
                is_matured=True,
                is_fictitious=True,
                metadata_={"fictitious": True},
            )
            db.add(snap)
        await db.flush()

        # Point baseline_variant_id at the control
        control_variant = next(v for v in variants_created if v.is_control)
        experiment.baseline_variant_id = control_variant.id

        # ── Append-only evaluation (promising — not a winner) ─────
        evaluation = ExperimentEvaluation(
            organization_id=org.id,
            experiment_id=experiment.id,
            evaluated_at=datetime(2025, 4, 14, tzinfo=UTC),
            evaluation_state="promising",
            primary_metric="ctr",
            per_variant_result={
                str(variants_created[0].id): {"metric_value": 3.0, "is_control": True},
                str(variants_created[1].id): {
                    "metric_value": 4.0,
                    "relative_diff": 0.33,
                    "confidence": 0.71,
                },
            },
            confidence=0.71,
            data_window={"start": "2025-04-01", "end": "2025-04-14", "active_days": 14},
            matured_through=date(2025, 4, 14),
            limitations=[
                "[FICTITIOUS] peeking_risk: evaluated before window end",
                "[FICTITIOUS] confidence below min_confidence (0.71 < 0.75)",
            ],
            total_snapshots_used=2,
            engine_version="1.0.0",
            causal_attribution=True,  # CONTROLLED single-variable
            notes="[FICTITIOUS] Test variant trending up; needs more data before winner.",
            is_fictitious=True,
        )
        db.add(evaluation)
        await db.flush()

        # ── Optimization decision (suggest only — NO budget change) ─
        decision = OptimizationDecision(
            organization_id=org.id,
            experiment_id=experiment.id,
            evaluation_id=evaluation.id,
            period_start="2025-04-01",
            period_end="2025-04-14",
            primary_metric="ctr",
            result={"leading_variant": "test", "relative_diff": 0.33},
            confidence=0.71,
            limitations=["[FICTITIOUS] confidence below threshold"],
            recommendation="[FICTITIOUS] Continue collecting data. Test variant promising but not yet conclusive.",
            suggested_action="continue",
            # executed_action intentionally None — v1 never auto-acts on budget
            decided_at=datetime(2025, 4, 14, tzinfo=UTC),
            user_responsible_id=user.id,
        )
        db.add(decision)

        # ── Learnings (1 confirmed, 1 provisional) with mock embeddings ─
        def _mock_emb(text: str) -> list[float]:
            import hashlib

            digest = hashlib.sha256(text.encode()).digest()
            floats = [(b / 127.5) - 1.0 for b in digest]
            while len(floats) < 128:
                floats.extend(floats[: 128 - len(floats)])
            floats = floats[:128]
            norm = sum(f**2 for f in floats) ** 0.5 or 1.0
            return [f / norm for f in floats]

        learning_confirmed = Learning(
            organization_id=org.id,
            context="ecommerce / skincare feed ads",
            segment="women 25-45",
            product_id=product.id,
            placement="feed",
            format="single_image",
            objective="CONVERSIONS",
            observed_pattern="[FICTITIOUS] Ingredient-focused creatives outperform generic hero shots on CTR.",
            evidence={"experiments": ["Ad C vs Ad A"], "ctr_lift": 0.08},
            sample_size=62000,
            metrics={"ctr_control": 3.6, "ctr_variant": 3.9},
            limitations=[
                "[FICTITIOUS] single product category",
                "[FICTITIOUS] one season of data",
            ],
            confidence=0.82,
            status="confirmed",
            reviewed_at=datetime(2025, 4, 10, tzinfo=UTC),
            reviewed_by_id=user.id,
            review_comment="[FICTITIOUS] Corroborated across two experiments. Confirmed.",
            responsible_type="user",
            embedding=_mock_emb(
                "ingredient-focused creatives outperform generic hero shots"
            ),
            is_fictitious=True,
            metadata_={"fictitious": True},
            created_at=datetime(2025, 4, 10, tzinfo=UTC),
            updated_at=datetime(2025, 4, 10, tzinfo=UTC),
        )
        db.add(learning_confirmed)

        learning_provisional = Learning(
            organization_id=org.id,
            context="ecommerce / skincare feed ads",
            segment="women 25-45",
            product_id=product.id,
            placement="feed",
            format="single_image",
            objective="CONVERSIONS",
            observed_pattern="[FICTITIOUS] Pink gradient backgrounds may lift CTR vs white backgrounds.",
            evidence={"experiments": ["Background Color Test"], "ctr_lift": 0.01},
            sample_size=28500,
            metrics={"ctr_control": 3.0, "ctr_variant": 4.0},
            limitations=[
                "[FICTITIOUS] confidence below threshold",
                "[FICTITIOUS] experiment still running",
            ],
            confidence=0.71,
            status="provisional",  # new learnings always start provisional
            responsible_type="agent",
            source_experiment_id=experiment.id,
            source_evaluation_id=evaluation.id,
            embedding=_mock_emb("pink gradient backgrounds lift ctr vs white"),
            is_fictitious=True,
            metadata_={"fictitious": True},
            created_at=datetime(2025, 5, 1, tzinfo=UTC),
            updated_at=datetime(2025, 5, 1, tzinfo=UTC),
        )
        db.add(learning_provisional)
        await db.flush()

        # ── Suggestion for next round (pending human approval) ────
        suggestion = ExperimentSuggestion(
            organization_id=org.id,
            source_experiment_id=experiment.id,
            selected_learning_ids=[str(learning_confirmed.id)],
            hypothesis="[FICTITIOUS] Combine ingredient callouts with a warm gradient background to maximize CTR.",
            primary_variable="composition",
            rationale="[FICTITIOUS] Builds on the confirmed ingredient-focus learning while exploring a new untested combination.",
            diversity_score=0.78,
            status="pending_approval",  # never auto-approved; no auto image/publish
            context_snapshot={"source": "Background Color Test", "learnings_used": 1},
        )
        db.add(suggestion)
        await db.flush()

        usage = LearningUsage(
            organization_id=org.id,
            learning_id=learning_confirmed.id,
            suggestion_id=suggestion.id,
            used_at=datetime.now(UTC),
        )
        db.add(usage)

        await db.commit()
        print("[seed] Phase 7: experiment (running) + 2 variants + 2 snapshots created")
        print(
            "[seed] Phase 7: 1 evaluation (promising) + 1 decision (continue, no budget change)"
        )
        print(
            "[seed] Phase 7: 2 learnings (1 confirmed, 1 provisional) + 1 suggestion (pending_approval)"
        )
        print("[seed] DONE. Seed complete!")
        print("[seed] Login: admin@demo.example / demo1234")


if __name__ == "__main__":
    asyncio.run(run_seed())
