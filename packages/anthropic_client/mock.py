"""
Mock Anthropic client — deterministic, no external API, no API key required.
Returns all Phase 3 segregated fields (observations / metric_facts / limitations).
"""
from __future__ import annotations

import time

from .image_guard import MediaKind, detect_media_kind
from .interface import (
    AnalysisEnvelope,
    AnalysisRequest,
    AnalysisResult,
    ColorLighting,
    CompositionInfo,
    HierarchyInfo,
    MetricFact,
    Observation,
    PerformanceHypothesis,
    ProductPresentation,
    TextAnalysis,
    UsageInfo,
)


class MockAnthropicClient:
    """Deterministic mock — returns structured analysis without any external call."""

    MODEL = "mock-claude-v3"

    async def analyze(
        self,
        request: AnalysisRequest,
        *,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> AnalysisEnvelope:
        t0 = time.monotonic()

        media_kind: MediaKind = detect_media_kind(request.image_path, request.image_url)

        # Video/carousel — return partial status (real provider would raise)
        if media_kind in ("video", "carousel"):
            result = AnalysisResult(
                visual_summary=f"[MOCK] Media kind '{media_kind}' is not supported for visual analysis.",
                limitations=[
                    f"Visual analysis is not available for {media_kind} creatives.",
                    "Submit an image creative for full analysis.",
                ],
            )
            return AnalysisEnvelope(
                result=result,
                model_used=self.MODEL,
                latency_ms=int((time.monotonic() - t0) * 1000),
                status="partial",
                repaired=False,
            )

        metrics = request.metrics or {}
        spend = metrics.get("spend") or 0
        roas = metrics.get("roas") or 0
        impressions = metrics.get("impressions") or 0
        ctr = metrics.get("ctr") or 0
        is_winner = bool(roas and roas > 2.0)
        is_loser = bool(spend and spend > 100 and (not roas or roas < 1.0))
        has_metrics = bool(metrics)
        has_image = bool(request.image_path or request.image_url)

        observations = [
            Observation(
                text="[mock observation] Product occupies approximately 60% of the frame.",
                category="composition",
            ),
            Observation(
                text="[mock observation] Visual hierarchy flows top-to-bottom: image → headline → CTA.",
                category="composition",
            ),
            Observation(
                text="[mock observation] Neutral colour palette with high contrast.",
                category="color",
            ),
        ]
        if request.headline:
            observations.append(
                Observation(
                    text=f"[mock observation] Headline '{request.headline[:60]}' is present and prominent.",
                    category="text",
                )
            )
        if not has_image:
            observations.append(
                Observation(
                    text="[mock observation] No image was provided; analysis is text-only.",
                    category="other",
                )
            )

        metric_facts: list[MetricFact] = []
        if has_metrics:
            if spend:
                metric_facts.append(MetricFact(text=f"Total spend: {spend}", metric="spend", value=float(spend)))
            if roas:
                metric_facts.append(MetricFact(text=f"ROAS: {roas}", metric="roas", value=float(roas)))
            if impressions:
                metric_facts.append(MetricFact(text=f"Impressions: {impressions}", metric="impressions", value=float(impressions)))
            if ctr:
                metric_facts.append(MetricFact(text=f"CTR: {ctr}%", metric="ctr", value=float(ctr)))
        else:
            metric_facts.append(
                MetricFact(text="[mock] No performance metrics were provided.", metric=None, value=None)
            )

        hypotheses = [
            PerformanceHypothesis(
                statement=(
                    "[mock hypothesis — not proven] The product-centred layout may correlate with "
                    f"{'higher' if is_winner else 'lower'} purchase intent based on available metrics."
                ),
                primary_variable="composition",
                expected_effect="higher_ctr" if is_winner else "lower_ctr",
                confidence=0.5,
            ),
            PerformanceHypothesis(
                statement="[mock hypothesis — not proven] Adding lifestyle context could improve CTR.",
                primary_variable="background",
                expected_effect="higher_ctr",
                confidence=0.4,
            ),
        ]

        limitations: list[str] = []
        if not has_image:
            limitations.append("No image was provided; visual observations are unavailable.")
        if not has_metrics:
            limitations.append("No performance metrics were provided; metric-based conclusions are unavailable.")
        limitations.append("[mock] Causal attribution requires a controlled experiment; these are correlations at best.")

        result = AnalysisResult(
            visual_summary=(
                f"[FICTITIOUS — MOCK ANALYSIS] Ad '{request.ad_name}' for product "
                f"'{request.product_name or 'unknown'}'. "
                "This analysis was generated by the mock provider and does not reflect real data."
            ),
            observations=observations,
            metric_facts=metric_facts,
            limitations=limitations,
            composition=CompositionInfo(
                layout="product-centered",
                thirds_rule=True,
                note="[mock observation] Product fills most of the frame.",
            ),
            hierarchy=HierarchyInfo(
                primary_element="product image",
                secondary_element="headline text",
                cta_position="bottom-right",
                note="[mock observation] Visual hierarchy flows top-to-bottom.",
            ),
            product_presentation=ProductPresentation(
                angle="front-facing",
                context="white background",
                note="[mock observation] Clean product shot with no lifestyle context.",
            ),
            color_and_lighting=ColorLighting(
                dominant_colors=["#FFFFFF", "#000000"],
                lighting="studio",
                note="[mock observation] Neutral palette; high contrast.",
            ),
            text_analysis=TextAnalysis(
                word_count=12,
                headline_present=bool(request.headline),
                cta_present=bool(request.cta),
                note="[mock observation] Short copy; CTA is prominent.",
            ),
            attention_elements=["[mock] product size", "[mock] colour contrast", "[mock] CTA button"],
            strengths=(
                ["[mock strength] High visual clarity", "[mock strength] Clear CTA"]
                if is_winner
                else ["[mock strength] Clean composition"]
            ),
            weaknesses=(
                ["[mock weakness] No social proof", "[mock weakness] Low emotional appeal"]
                if is_loser
                else ["[mock weakness] Generic background"]
            ),
            performance_hypotheses=hypotheses,
            elements_to_preserve=["[mock] product framing", "[mock] CTA placement"],
            elements_to_test=["[mock] background colour", "[mock] headline copy", "[mock] CTA text"],
            policy_risks=[],
            confidence=0.5,
        )

        return AnalysisEnvelope(
            result=result,
            model_used=self.MODEL,
            usage=UsageInfo(input_tokens=0, output_tokens=0),
            estimated_cost_usd=0.0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            status="completed",
            repaired=False,
        )

    async def health_check(self) -> bool:
        return True
