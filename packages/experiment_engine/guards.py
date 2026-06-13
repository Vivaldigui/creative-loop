"""
Experiment guards — pure validation functions.

Each guard returns an ExperimentGuardResult.  All guards must pass for
an experiment to start.  CONTROLLED experiments enforce single-variable
isolation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExperimentGuardResult:
    code: str
    severity: str  # "pass" | "warning" | "blocked"
    passed: bool
    detail: str = ""


@dataclass
class ExperimentGuardContext:
    mode: str  # EXPLORATORY | CONTROLLED
    primary_variable: str | None
    variants: list[dict[str, Any]]  # list of variant dicts with changed_variables, allocated_budget, audience
    has_baseline: bool
    window_start: str | None
    window_end: str | None
    planned_budget: float | None
    max_experiment_budget: float | None
    # Guard settings
    budget_tolerance_pct: float = 0.15
    extra: dict[str, Any] = field(default_factory=dict)


# ── Individual guards ─────────────────────────────────────────────────────────

def guard_controlled_single_variable(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    """CONTROLLED: each test variant must have exactly 1 changed_variable == primary_variable."""
    if ctx.mode != "CONTROLLED":
        return ExperimentGuardResult(
            code="skip_exploratory_variable_check",
            severity="pass",
            passed=True,
            detail="EXPLORATORY mode: multiple variables allowed.",
        )
    # No variants yet — skip (draft creation)
    if not ctx.variants:
        return ExperimentGuardResult(code="no_variants_skip", severity="pass", passed=True)
    if not ctx.primary_variable:
        return ExperimentGuardResult(
            code="controlled_missing_primary_variable",
            severity="blocked",
            passed=False,
            detail="CONTROLLED experiment requires primary_variable.",
        )
    test_variants = [v for v in ctx.variants if not v.get("is_control", False)]
    violations = []
    for v in test_variants:
        changed = v.get("changed_variables") or []
        if len(changed) != 1:
            violations.append(
                f"Variant '{v.get('name')}' has {len(changed)} changed_variables (expected 1)."
            )
        elif changed[0] != ctx.primary_variable:
            violations.append(
                f"Variant '{v.get('name')}' changes '{changed[0]}' but primary_variable is '{ctx.primary_variable}'."
            )
    if violations:
        return ExperimentGuardResult(
            code="controlled_multiple_variables",
            severity="blocked",
            passed=False,
            detail="; ".join(violations),
        )
    return ExperimentGuardResult(
        code="controlled_single_variable_ok",
        severity="pass",
        passed=True,
        detail=f"All test variants change only '{ctx.primary_variable}'.",
    )


def guard_has_baseline(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    # No variants yet — experiment is being created as draft, warn but don't block
    if not ctx.variants:
        return ExperimentGuardResult(
            code="no_variants_yet",
            severity="warning",
            passed=True,
            detail="No variants defined. Add a control variant before starting.",
        )
    if not ctx.has_baseline:
        return ExperimentGuardResult(
            code="missing_baseline_variant",
            severity="blocked",
            passed=False,
            detail="Experiment must have exactly one variant with is_control=True.",
        )
    return ExperimentGuardResult(code="has_baseline", severity="pass", passed=True)


def guard_each_variant_has_hypothesis(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    missing = [v.get("name", str(v.get("id", "?"))) for v in ctx.variants if not v.get("hypothesis")]
    if missing:
        return ExperimentGuardResult(
            code="variant_missing_hypothesis",
            severity="warning",
            passed=True,
            detail=f"Variants without hypothesis: {missing}. Add hypothesis for better traceability.",
        )
    return ExperimentGuardResult(code="all_variants_have_hypothesis", severity="pass", passed=True)


def guard_controlled_comparable_budget(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    if ctx.mode != "CONTROLLED":
        return ExperimentGuardResult(code="skip_budget_check", severity="pass", passed=True)
    budgets = [v.get("allocated_budget") for v in ctx.variants if v.get("allocated_budget") is not None]
    if len(budgets) < 2:
        return ExperimentGuardResult(
            code="budget_not_set", severity="warning", passed=True,
            detail="Variant budgets not set — comparability cannot be verified.",
        )
    mean_b = sum(budgets) / len(budgets)
    if mean_b <= 0:
        return ExperimentGuardResult(code="budget_zero", severity="warning", passed=True)
    max_deviation = max(abs(b - mean_b) / mean_b for b in budgets)
    if max_deviation > ctx.budget_tolerance_pct:
        return ExperimentGuardResult(
            code="controlled_unequal_budgets",
            severity="warning",
            passed=True,
            detail=f"Max budget deviation {max_deviation:.1%} > {ctx.budget_tolerance_pct:.1%}. "
                   "Comparable budgets improve causal inference.",
        )
    return ExperimentGuardResult(code="comparable_budgets", severity="pass", passed=True)


def guard_controlled_comparable_audience(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    if ctx.mode != "CONTROLLED":
        return ExperimentGuardResult(code="skip_audience_check", severity="pass", passed=True)
    audiences = [v.get("audience") for v in ctx.variants if v.get("audience") is not None]
    if len(audiences) < 2:
        return ExperimentGuardResult(
            code="audience_not_set", severity="warning", passed=True,
            detail="Variant audiences not set — comparability cannot be verified.",
        )
    hashes = {hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest() for a in audiences}
    if len(hashes) > 1:
        return ExperimentGuardResult(
            code="controlled_different_audiences",
            severity="warning",
            passed=True,
            detail="Variants have different audience definitions. This reduces causal inference quality.",
        )
    return ExperimentGuardResult(code="comparable_audiences", severity="pass", passed=True)


def guard_controlled_comparable_window(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    if ctx.mode != "CONTROLLED":
        return ExperimentGuardResult(code="skip_window_check", severity="pass", passed=True)
    if not ctx.window_start or not ctx.window_end:
        return ExperimentGuardResult(
            code="window_not_set", severity="warning", passed=True,
            detail="No experiment window defined — maturation tracking will be limited.",
        )
    return ExperimentGuardResult(code="window_set", severity="pass", passed=True)


def guard_experiment_budget(ctx: ExperimentGuardContext) -> ExperimentGuardResult:
    if ctx.planned_budget is None or ctx.max_experiment_budget is None:
        return ExperimentGuardResult(code="budget_not_capped", severity="pass", passed=True)
    if ctx.planned_budget > ctx.max_experiment_budget:
        return ExperimentGuardResult(
            code="experiment_budget_exceeded",
            severity="blocked",
            passed=False,
            detail=f"Planned budget {ctx.planned_budget} > MAX_EXPERIMENT_BUDGET {ctx.max_experiment_budget}.",
        )
    return ExperimentGuardResult(code="budget_within_limit", severity="pass", passed=True)


# ── Run all guards ────────────────────────────────────────────────────────────

_GUARD_SEQUENCE = [
    guard_has_baseline,
    guard_controlled_single_variable,
    guard_each_variant_has_hypothesis,
    guard_controlled_comparable_budget,
    guard_controlled_comparable_audience,
    guard_controlled_comparable_window,
    guard_experiment_budget,
]


def run_experiment_guards(ctx: ExperimentGuardContext) -> list[ExperimentGuardResult]:
    return [g(ctx) for g in _GUARD_SEQUENCE]


def has_blocking_failure(results: list[ExperimentGuardResult]) -> bool:
    return any(r.severity == "blocked" for r in results)
