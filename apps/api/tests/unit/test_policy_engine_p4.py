"""Phase 4 policy engine tests — segment-aware rules, internal notice, no Meta approval claim."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from packages.policy_engine.engine import RESULT_BLOCKED, RESULT_PASS, PolicyEngine


def engine() -> PolicyEngine:
    return PolicyEngine()


# ── internal notice ────────────────────────────────────────────────

def test_internal_notice_present():
    result = engine().check(text="A clean ad")
    assert result.internal_notice
    assert "Meta" in result.internal_notice or "não garante" in result.internal_notice.lower() or "never" in result.internal_notice.lower()


def test_internal_notice_never_claims_meta_approval():
    result = engine().check(text="")
    notice = result.internal_notice.lower()
    # Notice must not positively claim Meta approval
    assert "aprovado pela meta" not in notice
    assert "approved by meta" not in notice


# ── clean text ────────────────────────────────────────────────────

def test_clean_text_passes():
    result = engine().check(text="Beautiful product photo with natural lighting.")
    assert result.result == RESULT_PASS


# ── blocked rules ─────────────────────────────────────────────────

def test_weight_loss_guarantee_blocked():
    result = engine().check(text="Perca 10kg garantido em apenas 30 dias!")
    assert result.result == RESULT_BLOCKED
    assert any(f.severity == "blocked" for f in result.findings)


def test_medical_cure_claim_blocked():
    result = engine().check(text="Este suplemento cura a diabetes e o câncer.")
    assert result.result == RESULT_BLOCKED


def test_prohibited_financial_claim_blocked():
    result = engine().check(text="Faça mais dinheiro garantido ainda este mês!")
    blocked = [f for f in result.findings if f.severity == "blocked"]
    assert blocked or result.result == RESULT_BLOCKED


# ── discrimination / hate speech ─────────────────────────────────

def test_discrimination_blocked():
    result = engine().check(text="Sem discriminação racial ou qualquer preconceito.")
    # "discriminação" and "preconceito" match the pattern
    assert result.result == RESULT_BLOCKED


# ── rule_set_version ──────────────────────────────────────────────

def test_rule_set_version_present():
    result = engine().check(text="Normal ad text here.")
    assert result.rule_set_version
    assert isinstance(result.rule_set_version, str)


# ── findings have required fields ─────────────────────────────────

def test_blocked_finding_has_detail():
    result = engine().check(text="Lose weight fast, guaranteed results!")
    for finding in result.findings:
        assert finding.detail or finding.rule
