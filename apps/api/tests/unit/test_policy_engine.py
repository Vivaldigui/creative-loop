"""Unit tests for policy engine."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from packages.policy_engine.engine import RESULT_BLOCKED, RESULT_PASS, RESULT_WARNING, PolicyEngine


def test_clean_text_passes():
    engine = PolicyEngine()
    result = engine.check("Beautiful skincare product. Shop now.")
    assert result.result == RESULT_PASS
    assert result.findings == []


def test_guarantee_is_blocked():
    engine = PolicyEngine()
    result = engine.check("Garantimos resultados em 7 dias!")
    assert result.result == RESULT_BLOCKED
    assert any(f.rule == "guarantee_of_result" for f in result.findings)


def test_medical_claim_is_blocked():
    engine = PolicyEngine()
    result = engine.check("Trata acne e cura a pele em 3 dias.")
    assert result.result == RESULT_BLOCKED


def test_urgency_is_warning():
    engine = PolicyEngine()
    result = engine.check("Oferta urgente! Não perca essa chance.")
    assert result.result in (RESULT_WARNING, RESULT_BLOCKED)


def test_before_after_is_blocked():
    engine = PolicyEngine()
    result = engine.check("Veja as fotos antes e depois do tratamento.")
    assert result.result == RESULT_BLOCKED
