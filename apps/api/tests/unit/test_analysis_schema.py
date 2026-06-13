"""
Unit tests for AnalysisResult Pydantic schema (Phase 3).
Tests: valid, invalid JSON, incomplete, unknown fields, confidence clamping.
"""
from __future__ import annotations

import pytest
from packages.anthropic_client.interface import AnalysisResult, Observation
from pydantic import ValidationError

# ── Valid schema ──────────────────────────────────────────────────

def test_valid_full_schema():
    data = {
        "visual_summary": "Test ad",
        "observations": [{"text": "Product centred", "category": "composition"}],
        "metric_facts": [{"text": "CTR 3%", "metric": "ctr", "value": 3.0}],
        "limitations": ["No image provided"],
        "composition": {"layout": "grid"},
        "hierarchy": {"primary_element": "image"},
        "product_presentation": {"angle": "front"},
        "color_and_lighting": {"dominant_colors": ["#fff"], "lighting": "studio"},
        "text_analysis": {"word_count": 5},
        "attention_elements": ["logo"],
        "strengths": ["Clear CTA"],
        "weaknesses": ["Generic"],
        "performance_hypotheses": [
            {"statement": "X improves CTR", "primary_variable": "composition", "confidence": 0.6}
        ],
        "elements_to_preserve": ["logo"],
        "elements_to_test": ["background"],
        "policy_risks": [],
        "confidence": 0.75,
    }
    result = AnalysisResult.model_validate(data)
    assert result.confidence == 0.75
    assert result.observations[0].category == "composition"
    assert result.performance_hypotheses[0].confidence == 0.6


# ── Unknown fields ignored ────────────────────────────────────────

def test_unknown_fields_ignored():
    data = {
        "visual_summary": "ok",
        "totally_unknown_field": "should be dropped",
        "another_one": 99,
    }
    result = AnalysisResult.model_validate(data)
    assert not hasattr(result, "totally_unknown_field")


# ── Confidence clamping ───────────────────────────────────────────

def test_confidence_clamped_above_1():
    result = AnalysisResult.model_validate({"confidence": 1.5})
    assert result.confidence == 1.0


def test_confidence_clamped_below_0():
    result = AnalysisResult.model_validate({"confidence": -0.3})
    assert result.confidence == 0.0


def test_confidence_invalid_string_defaults_0():
    result = AnalysisResult.model_validate({"confidence": "not_a_number"})
    assert result.confidence == 0.0


# ── Incomplete / partial JSON ─────────────────────────────────────

def test_incomplete_json_uses_defaults():
    result = AnalysisResult.model_validate({"visual_summary": "partial"})
    assert result.observations == []
    assert result.metric_facts == []
    assert result.limitations == []
    assert result.confidence == 0.0


def test_empty_dict_uses_defaults():
    result = AnalysisResult.model_validate({})
    assert result.visual_summary == ""
    assert result.confidence == 0.0


# ── Observation category ──────────────────────────────────────────

def test_observation_unknown_category_raises():
    """Unknown category literal raises ValidationError (strict typing enforced)."""
    with pytest.raises(ValidationError):
        Observation.model_validate({"text": "something", "category": "made_up_cat"})


def test_observation_valid_categories():
    for cat in ("composition", "color", "text", "product", "attention", "style", "other"):
        obs = Observation.model_validate({"text": "x", "category": cat})
        assert obs.category == cat


# ── to_storage_dict ───────────────────────────────────────────────

def test_to_storage_dict_is_plain_dict():
    result = AnalysisResult.model_validate({"visual_summary": "test", "confidence": 0.8})
    d = result.to_storage_dict()
    assert isinstance(d, dict)
    assert d["visual_summary"] == "test"
    assert d["confidence"] == 0.8
    # Should not contain Pydantic model objects
    assert isinstance(d["observations"], list)
