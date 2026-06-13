from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

RESULT_PASS = "PASS"
RESULT_WARNING = "WARNING"
RESULT_BLOCKED = "BLOCKED"

# IMPORTANT: The system never declares that a creative is approved by Meta.
# This is solely an internal compliance check.
INTERNAL_ONLY_NOTICE = (
    "This creative passed the internal policy check. "
    "This does NOT guarantee approval by Meta Ads or any other platform."
)


class PolicyFinding(BaseModel):
    rule: str
    severity: Literal["warning", "blocked"]
    detail: str
    matched_text: str | None = None
    segment: str | None = None


class PolicyResult(BaseModel):
    result: str  # PASS | WARNING | BLOCKED
    findings: list[PolicyFinding]
    rule_set_version: str = "2.0.0"
    internal_notice: str = INTERNAL_ONLY_NOTICE


# ── Rule definitions ─────────────────────────────────────────────
# (pattern, severity, label, segments_override)
# segments_override=None means rule applies to all segments
_RuleSpec = tuple[re.Pattern, str, str, set[str] | None]

_BASE_RULES: list[_RuleSpec] = [
    # BLOCKED — universal
    (re.compile(r"\bgarant(o|ia|ido|imos|em)\b", re.I), "blocked", "guarantee_of_result", None),
    (re.compile(r"\bcura\b|\bcurar\b|\btratamento\b|\btrat(a|ou)\b", re.I), "blocked", "medical_treatment_claim", None),
    (re.compile(r"\bantes?\s+e\s+depois\b", re.I), "blocked", "before_after_comparison", None),
    (re.compile(r"\bperca\s+\d+\s*kg\b|\bemagre(ce|ça|ça)\s+\d+\s*kg\b", re.I), "blocked", "weight_loss_guarantee", None),
    (re.compile(r"\b100%\s+(eficaz|efetivo|natural|seguro|comprovado)\b", re.I), "blocked", "absolute_claim", None),
    (re.compile(r"\bcura\s+(definitiva|total|permanente)\b", re.I), "blocked", "cure_claim", None),
    (re.compile(r"\batributos?\s+(pessoal|racial|religios|sexual|ét)", re.I), "blocked", "personal_attribute_targeting", None),
    (re.compile(r"\bdiscriminaç|discriminar|preconceito|racismo\b", re.I), "blocked", "discriminatory_language", None),
    (re.compile(r"\bfaça\s+mais\s+dinheiro\s+garantido\b|\brenda\s+extra\s+garantida\b", re.I), "blocked", "income_guarantee", None),

    # WARNING — universal
    (re.compile(r"\burgente?\b|\batençã?o!\b|\bnão\s+perca\b|\búltimas?\s+vagas?\b", re.I), "warning", "false_urgency", None),
    (re.compile(r"\bmelhor\s+(do\s+)?(mundo|brasil|mercado)\b", re.I), "warning", "superlative_claim", None),
    (re.compile(r"\bmédico\b|\bdoctor\b|\bdr\.\b|\bdrª?\.\b", re.I), "warning", "medical_reference", None),
    (re.compile(r"\bgrátis\b|\bfree\b|\bde\s+graça\b", re.I), "warning", "free_claim", None),
    (re.compile(r"\bpremium\b|\bexclusivo\b|\bvip\b", re.I), "warning", "exclusivity_claim", None),
    (re.compile(r"\bcomprovad(o|a)\b|\bclínic(o|a|amente)\b", re.I), "warning", "unverified_claim", None),
    (re.compile(r"\bpreço\s+imperdível\b|\boferta\s+imperdível\b", re.I), "warning", "price_sensationalism", None),
    (re.compile(r"\b(R\$|BRL|USD|\$)\s*\d+[\d.,]*\b", re.I), "warning", "price_mention", None),
    (re.compile(r"\btm\b|\b®\b|\b©\b", re.I), "warning", "third_party_trademark", None),

    # Segment-specific: health / wellness / fitness
    (re.compile(r"\bemagrecimento\s+rápido\b|\bperda\s+de\s+peso\s+rápida?\b", re.I), "blocked", "rapid_weight_loss", {"health", "fitness", "beauty"}),
    (re.compile(r"\balegaç(ão|ões)\s+médica\b|\baprovado\s+pela?\s+(anvisa|fda|oms)\b", re.I), "blocked", "medical_approval_claim", {"health", "fitness"}),
    (re.compile(r"\bnatural\b.*\bsem\s+efeitos?\s+colaterais?\b|\bsem\s+contraindicaç", re.I), "warning", "natural_without_side_effects", {"health", "beauty", "fitness"}),
]


class PolicyEngine:
    """
    Configurable policy engine with segment-aware rule application.

    Result classification:
    - BLOCKED: creative cannot be published without human override by owner.
    - WARNING: reviewer should validate before approval.
    - PASS: no flags found.

    IMPORTANT: PASS does NOT mean the creative is approved by Meta or any platform.
    """

    def __init__(self, rule_set_version: str = "2.0.0") -> None:
        self._version = rule_set_version

    def check(self, text: str, segment: str | None = None) -> PolicyResult:
        """
        Check `text` (prompt + copy) against all applicable policy rules.

        `segment` selects additional segment-specific rules (e.g. "health", "fitness").
        """
        findings: list[PolicyFinding] = []

        for pattern, severity, label, segments in _BASE_RULES:
            # Apply rule if it's universal or matches the current segment
            if segments is not None and segment not in segments:
                continue
            m = pattern.search(text)
            if m:
                findings.append(PolicyFinding(
                    rule=label,
                    severity=severity,
                    detail=f"Pattern '{pattern.pattern}' matched in creative text.",
                    matched_text=m.group(0),
                    segment=segment,
                ))

        if any(f.severity == "blocked" for f in findings):
            result = RESULT_BLOCKED
        elif findings:
            result = RESULT_WARNING
        else:
            result = RESULT_PASS

        return PolicyResult(
            result=result,
            findings=findings,
            rule_set_version=self._version,
        )
