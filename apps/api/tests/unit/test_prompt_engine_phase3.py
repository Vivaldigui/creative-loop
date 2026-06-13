"""
Unit tests for extended PromptEngine (Phase 3).
"""
from __future__ import annotations

import pytest
from packages.prompt_engine.engine import PromptEngine, PromptFields


@pytest.fixture
def engine():
    return PromptEngine()


def test_build_includes_new_fields(engine):
    fields = PromptFields(
        product_name="Glow Pro",
        channel="Instagram Feed",
        positioning="Premium skincare for busy women",
        exact_text="50% off today only",
        mandatory_elements="Logo bottom-right",
        learnings_used="Lifestyle background increases CTR",
        known_limitations="Small sample size; provisional only",
    )
    text = engine.build(fields)
    assert "CHANNEL: Instagram Feed" in text
    assert "POSITIONING: Premium skincare" in text
    assert "EXACT TEXT: 50% off today only" in text
    assert "MANDATORY ELEMENTS: Logo bottom-right" in text
    assert "LEARNINGS APPLIED:" in text
    assert "KNOWN LIMITATIONS:" in text


def test_build_is_deterministic(engine):
    fields = PromptFields(product_name="A", cta_text="B", objective="C")
    assert engine.build(fields) == engine.build(fields)


def test_content_hash_changes_when_fields_change(engine):
    f1 = PromptFields(cta_text="Buy")
    f2 = PromptFields(cta_text="Order")
    h1 = engine.content_hash(engine.build(f1))
    h2 = engine.content_hash(engine.build(f2))
    assert h1 != h2


def test_new_version_has_content_hash(engine):
    fields = PromptFields(product_name="Widget", cta_text="Buy")
    v = engine.new_version(fields, parent_text=None, parent_version=0, change_reason="init")
    assert v.content_hash is not None
    assert len(v.content_hash) == 64  # sha256 hex


def test_diff_shows_changed_line(engine):
    fields_a = PromptFields(cta_text="Shop Now")
    fields_b = PromptFields(cta_text="Buy Now")
    text_a = engine.build(fields_a)
    text_b = engine.build(fields_b)
    diff = engine.diff(text_a, text_b)
    assert "-CTA: Shop Now" in diff
    assert "+CTA: Buy Now" in diff


def test_new_version_number_increments(engine):
    fields = PromptFields(cta_text="CTA")
    v1 = engine.new_version(fields, parent_text=None, parent_version=0, change_reason="init")
    v2 = engine.new_version(fields, parent_text=v1.prompt_text, parent_version=1, change_reason="rev")
    assert v1.version_number == 1
    assert v2.version_number == 2


def test_all_sections_rendered_in_order(engine):
    fields = PromptFields(
        objective="sell",
        product_name="P",
        ad_format="feed",
        cta_text="go",
        originality_note="original",
    )
    text = engine.build(fields)
    lines = text.splitlines()
    labels = [line.split(":")[0] for line in lines]
    # OBJECTIVE should come before PRODUCT which should come before FORMAT
    assert labels.index("OBJECTIVE") < labels.index("PRODUCT")
    assert labels.index("PRODUCT") < labels.index("FORMAT")
