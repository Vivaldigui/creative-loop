"""Unit tests for prompt engine — versioning is critical."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from packages.prompt_engine.engine import PromptEngine, PromptFields


def test_initial_version():
    engine = PromptEngine()
    fields = PromptFields(product_name="ProductX", objective="Drive sales", cta_text="Buy Now")
    v = engine.new_version(fields, parent_text=None, parent_version=0, change_reason="initial")
    assert v.version_number == 1
    assert "ProductX" in v.prompt_text
    assert "Buy Now" in v.prompt_text
    assert v.diff_summary is None


def test_revision_creates_new_version_with_diff():
    engine = PromptEngine()
    fields1 = PromptFields(product_name="ProductX", cta_text="Buy Now")
    v1 = engine.new_version(fields1, parent_text=None, parent_version=0, change_reason="initial")

    fields2 = PromptFields(product_name="ProductX", cta_text="Shop Now")
    v2 = engine.new_version(fields2, parent_text=v1.prompt_text, parent_version=1, change_reason="changed CTA")

    assert v2.version_number == 2
    assert v2.diff_summary is not None
    assert "Buy Now" in v2.diff_summary or "Shop Now" in v2.diff_summary
    # Old text is NOT overwritten — v1 text is unchanged
    assert "Buy Now" in v1.prompt_text
    assert "Shop Now" in v2.prompt_text


def test_originality_note_always_present():
    engine = PromptEngine()
    fields = PromptFields(product_name="X")
    v = engine.new_version(fields, parent_text=None, parent_version=0, change_reason="test")
    assert "original" in v.prompt_text.lower()
