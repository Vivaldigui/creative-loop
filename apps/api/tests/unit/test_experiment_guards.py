"""Unit tests for experiment_engine.guards."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from packages.experiment_engine.guards import (
    ExperimentGuardContext,
    guard_controlled_single_variable,
    guard_each_variant_has_hypothesis,
    guard_has_baseline,
    has_blocking_failure,
    run_experiment_guards,
)


def make_variant_dict(id: str, is_control: bool = False, hypothesis: str = "H", changed_vars: list | None = None):
    return {
        "id": id,
        "name": f"variant_{id}",
        "is_control": is_control,
        "hypothesis": hypothesis,
        "changed_variables": changed_vars or ["headline"],
        "allocated_budget": None,
        "audience": None,
    }


def make_ctx(mode="CONTROLLED", variants=None, has_baseline=True, budget=None):
    if variants is None:
        variants = [make_variant_dict("v1", is_control=True), make_variant_dict("v2")]
    return ExperimentGuardContext(
        mode=mode,
        primary_variable="headline",
        variants=variants,
        has_baseline=has_baseline,
        window_start=None,
        window_end=None,
        planned_budget=budget or 500.0,
        max_experiment_budget=None,
    )


class TestGuardHasBaseline:
    def test_passes_when_baseline_present(self):
        ctx = make_ctx(has_baseline=True)
        result = guard_has_baseline(ctx)
        assert result.passed

    def test_blocks_when_has_variants_but_no_baseline(self):
        ctx = make_ctx(has_baseline=False)  # has variants but none is_control
        result = guard_has_baseline(ctx)
        assert not result.passed
        assert result.severity == "blocked"

    def test_warns_when_no_variants(self):
        ctx = make_ctx(variants=[], has_baseline=False)
        result = guard_has_baseline(ctx)
        assert result.passed  # warning, not block
        assert result.severity == "warning"


class TestGuardControlledSingleVariable:
    def test_passes_with_one_variable(self):
        ctx = make_ctx(mode="CONTROLLED")
        result = guard_controlled_single_variable(ctx)
        assert result.passed

    def test_blocks_with_multiple_variables(self):
        v1 = make_variant_dict("v1", is_control=True, changed_vars=[])
        v2 = make_variant_dict("v2", changed_vars=["headline", "image"])
        ctx = make_ctx(mode="CONTROLLED", variants=[v1, v2])
        result = guard_controlled_single_variable(ctx)
        assert not result.passed
        assert result.severity == "blocked"

    def test_passes_for_exploratory_even_with_multiple(self):
        v2 = make_variant_dict("v2", changed_vars=["headline", "image", "cta"])
        ctx = make_ctx(mode="EXPLORATORY", variants=[make_variant_dict("v1", is_control=True), v2])
        result = guard_controlled_single_variable(ctx)
        assert result.passed


class TestGuardVariantHypothesis:
    def test_passes_when_all_have_hypothesis(self):
        ctx = make_ctx()
        result = guard_each_variant_has_hypothesis(ctx)
        assert result.passed

    def test_warns_when_missing(self):
        v1 = make_variant_dict("v1", is_control=True, hypothesis="")
        v2 = make_variant_dict("v2")
        ctx = make_ctx(variants=[v1, v2])
        result = guard_each_variant_has_hypothesis(ctx)
        assert result.severity == "warning"


class TestRunExperimentGuards:
    def test_valid_controlled_passes(self):
        ctx = make_ctx(mode="CONTROLLED")
        results = run_experiment_guards(ctx)
        assert not has_blocking_failure(results)

    def test_no_baseline_blocks(self):
        ctx = make_ctx(has_baseline=False)
        results = run_experiment_guards(ctx)
        assert has_blocking_failure(results)

    def test_controlled_multiple_vars_blocks(self):
        v1 = make_variant_dict("v1", is_control=True, changed_vars=[])
        v2 = make_variant_dict("v2", changed_vars=["a", "b"])
        ctx = make_ctx(mode="CONTROLLED", variants=[v1, v2])
        results = run_experiment_guards(ctx)
        assert has_blocking_failure(results)

    def test_exploratory_multiple_vars_does_not_block(self):
        v2 = make_variant_dict("v2", changed_vars=["a", "b", "c"])
        ctx = make_ctx(mode="EXPLORATORY", variants=[make_variant_dict("v1", is_control=True), v2])
        results = run_experiment_guards(ctx)
        assert not has_blocking_failure(results)
