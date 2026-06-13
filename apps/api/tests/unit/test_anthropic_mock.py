"""
Unit tests for MockAnthropicClient (Phase 3).
Verifies: no API key needed, all new fields populated, video/carousel partial.
"""
from __future__ import annotations

import pytest
from packages.anthropic_client.interface import AnalysisRequest
from packages.anthropic_client.mock import MockAnthropicClient


@pytest.fixture
def client():
    return MockAnthropicClient()


@pytest.fixture
def basic_request():
    return AnalysisRequest(
        ad_name="Test Ad",
        headline="Great product",
        body_text="Buy now",
        cta="Shop",
        product_name="Glow Pro",
        metrics={"spend": 200, "roas": 2.5, "impressions": 10000, "ctr": 3.0},
    )


# ── No API key needed ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_requires_no_api_key(basic_request):
    c = MockAnthropicClient()
    envelope = await c.analyze(basic_request)
    assert envelope.status == "completed"


# ── All Phase 3 fields populated ──────────────────────────────────

@pytest.mark.asyncio
async def test_observations_present(client, basic_request):
    env = await client.analyze(basic_request)
    assert len(env.result.observations) > 0
    for obs in env.result.observations:
        assert obs.text
        assert obs.category


@pytest.mark.asyncio
async def test_metric_facts_present_when_metrics_given(client, basic_request):
    env = await client.analyze(basic_request)
    assert len(env.result.metric_facts) > 0
    metrics_mentioned = {f.metric for f in env.result.metric_facts if f.metric}
    assert "roas" in metrics_mentioned or "spend" in metrics_mentioned


@pytest.mark.asyncio
async def test_limitations_present(client, basic_request):
    env = await client.analyze(basic_request)
    assert len(env.result.limitations) > 0


@pytest.mark.asyncio
async def test_confidence_in_range(client, basic_request):
    env = await client.analyze(basic_request)
    assert 0.0 <= env.result.confidence <= 1.0


@pytest.mark.asyncio
async def test_hypotheses_typed(client, basic_request):
    env = await client.analyze(basic_request)
    for h in env.result.performance_hypotheses:
        assert h.statement
        assert 0.0 <= h.confidence <= 1.0


# ── No metrics → limitation noted ────────────────────────────────

@pytest.mark.asyncio
async def test_no_metrics_noted_in_metric_facts(client):
    req = AnalysisRequest(ad_name="No metrics ad")
    env = await client.analyze(req)
    all_text = " ".join(f.text for f in env.result.metric_facts)
    assert "No" in all_text or "no" in all_text or "metric" in all_text.lower()


# ── No image → limitation noted ──────────────────────────────────

@pytest.mark.asyncio
async def test_no_image_noted_in_observations(client):
    req = AnalysisRequest(ad_name="Text only")
    env = await client.analyze(req)
    all_obs = " ".join(o.text for o in env.result.observations)
    assert "image" in all_obs.lower() or "No image" in all_obs


# ── Video → partial ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_video_returns_partial(client):
    req = AnalysisRequest(ad_name="Video ad", image_path="ad.mp4")
    env = await client.analyze(req)
    assert env.status == "partial"
    assert len(env.result.limitations) > 0


# ── Envelope metadata ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_envelope_usage_present(client, basic_request):
    env = await client.analyze(basic_request)
    assert env.usage is not None
    assert env.usage.input_tokens == 0  # mock returns 0
    assert env.usage.output_tokens == 0


@pytest.mark.asyncio
async def test_envelope_latency_ms_nonnegative(client, basic_request):
    env = await client.analyze(basic_request)
    assert env.latency_ms >= 0


# ── Health check ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    assert await client.health_check() is True
