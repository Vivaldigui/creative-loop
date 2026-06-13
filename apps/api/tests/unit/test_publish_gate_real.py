"""
Unit tests for real-mode publication guards.

Tests that:
- Guard sequence for real mode has 16 guards (dry-run has 13)
- guard_real_mode_enabled blocks when dry_run=True
- guard_write_enabled blocks when meta_write_enabled=False
- guard_credentials_valid blocks when credentials_valid=False
- Both interlock flags must be True for guards to pass
- Guards promoted from warning to blocked in real mode: min_config, landing_url
"""
from __future__ import annotations

import uuid

from app.services.publication_guards import (
    _DRY_RUN_GUARD_SEQUENCE,
    _REAL_GUARD_SEQUENCE,
    GuardContext,
    has_blocking_failure,
    run_all_guards,
)


def _base_ctx(**overrides) -> GuardContext:
    org = uuid.uuid4()
    defaults: dict = {
        "actor_role": "owner",
        "org_id": org,
        "creative_org_id": org,
        "creative_status": "approved",
        "creative_id": uuid.uuid4(),
        "has_approval": True,
        "approval_id": uuid.uuid4(),
        "has_blocked_quality_check": False,
        "has_blocked_policy_check": False,
        "daily_budget_brl": 50.0,
        "max_daily_spend": 200.0,
        "max_experiment_budget": None,
        "experiment_id": None,
        "experiment_budget_used": 0.0,
        "daily_simulated_count": 0,
        "max_daily_new_ads": 3,
        "landing_url": "https://example.com/lp",
        "objective": "OUTCOME_TRAFFIC",
        "optimization_goal": "LINK_CLICKS",
        "has_page_reference": True,
        "idempotency_key": "test-key-123",
        "previous_attempt_id": None,
        "previous_payload_hash": None,
        "current_payload_hash": "abc123",
        "idempotency_ttl_hours": 24,
        "require_human_approval": True,
        "dry_run": True,
        "meta_write_enabled": False,
        "credentials_valid": False,
        "audit_available": True,
    }
    defaults.update(overrides)
    return GuardContext(**defaults)


def test_dry_run_sequence_has_13_guards() -> None:
    assert len(_DRY_RUN_GUARD_SEQUENCE) == 13


def test_real_sequence_has_16_guards() -> None:
    assert len(_REAL_GUARD_SEQUENCE) == 16


def test_guard_real_mode_blocks_when_dry_run_true() -> None:
    ctx = _base_ctx(dry_run=True, meta_write_enabled=True, credentials_valid=True)
    results = run_all_guards(ctx, mode="real")
    blocked = [r for r in results if r.code == "real_mode_blocked_dry_run" and not r.passed]
    assert blocked, f"guard_real_mode_enabled should block when dry_run=True. Results: {[r.code for r in results]}"
    assert has_blocking_failure(results)


def test_guard_write_enabled_blocks_when_false() -> None:
    ctx = _base_ctx(dry_run=False, meta_write_enabled=False, credentials_valid=True)
    results = run_all_guards(ctx, mode="real")
    blocked = [r for r in results if r.code == "write_not_enabled" and not r.passed]
    assert blocked, f"guard_write_enabled should block when meta_write_enabled=False. Results: {[r.code for r in results]}"


def test_guard_credentials_valid_blocks_when_false() -> None:
    ctx = _base_ctx(dry_run=False, meta_write_enabled=True, credentials_valid=False)
    results = run_all_guards(ctx, mode="real")
    blocked = [r for r in results if r.code == "credentials_invalid" and not r.passed]
    assert blocked, f"guard_credentials_valid should block when credentials_valid=False. Results: {[r.code for r in results]}"


def test_both_interlock_flags_required() -> None:
    """Single-flag change alone should never enable real writes."""
    ctx = _base_ctx(dry_run=False, meta_write_enabled=False, credentials_valid=True)
    results = run_all_guards(ctx, mode="real")
    assert has_blocking_failure(results), "write_enabled=False should still block"


def test_real_mode_all_clear_passes() -> None:
    ctx = _base_ctx(
        dry_run=False,
        meta_write_enabled=True,
        credentials_valid=True,
        has_page_reference=True,
        landing_url="https://example.com",
    )
    results = run_all_guards(ctx, mode="real")
    blocked = [r for r in results if not r.passed and r.severity == "blocked"]
    assert not blocked, f"Expected no blocks, got: {[r.code for r in blocked]}"


def test_min_config_is_hard_block_in_real_mode() -> None:
    """In real mode, missing page_reference → min_config_missing (blocked)."""
    ctx = _base_ctx(
        dry_run=False,
        meta_write_enabled=True,
        credentials_valid=True,
        has_page_reference=False,  # triggers min_config check
    )
    results = run_all_guards(ctx, mode="real")
    blocked = [r for r in results if "min_config" in r.code and not r.passed]
    assert blocked, f"Expected min_config block in real mode, got: {[r.code for r in results]}"
    assert blocked[0].severity == "blocked"


def test_min_config_is_warning_only_in_dry_run_mode() -> None:
    """In DRY_RUN mode, missing page_reference → min_config_warnings (warning, passes=True)."""
    ctx = _base_ctx(dry_run=True, has_page_reference=False)
    results = run_all_guards(ctx, mode="dry_run")
    min_cfg = [r for r in results if "min_config" in r.code]
    assert min_cfg, f"Expected min_config result, got: {[r.code for r in results]}"
    # In DRY_RUN, warnings pass but with severity="warning"
    assert min_cfg[0].severity == "warning", "In DRY_RUN, min_config should be a warning"
    assert min_cfg[0].passed is True, "In DRY_RUN, min_config warning should still pass"


def test_landing_url_is_hard_block_in_real_mode() -> None:
    ctx = _base_ctx(
        dry_run=False,
        meta_write_enabled=True,
        credentials_valid=True,
        landing_url=None,
    )
    results = run_all_guards(ctx, mode="real")
    blocked = [r for r in results if "landing_url" in r.code and not r.passed]
    assert blocked, f"Expected landing_url block in real mode, got: {[r.code for r in results]}"
    assert blocked[0].severity == "blocked"
