"""Unit tests for publication guards — pure functions, no DB."""
from __future__ import annotations

import uuid

from app.services.publication_guards import (
    GuardContext,
    guard_approval_present,
    guard_budget_present,
    guard_creative_in_org,
    guard_creative_status,
    guard_daily_ads_count,
    guard_daily_spend_limit,
    guard_dry_run_enabled,
    guard_idempotency,
    guard_landing_url,
    guard_not_blocked,
    guard_rbac,
    has_blocking_failure,
    is_safe_retry,
    results_to_dict,
    run_all_guards,
)


def _ctx(**overrides) -> GuardContext:
    org = uuid.uuid4()
    defaults = {
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
        "landing_url": "https://example.com/product",
        "objective": "OUTCOME_TRAFFIC",
        "optimization_goal": "LINK_CLICKS",
        "has_page_reference": True,
        "idempotency_key": "test-key",
        "previous_attempt_id": None,
        "previous_payload_hash": None,
        "current_payload_hash": "abc123",
        "idempotency_ttl_hours": 24,
        "require_human_approval": True,
        "dry_run": True,
    }
    defaults.update(overrides)
    return GuardContext(**defaults)


class TestDryRunGuard:
    def test_passes_when_dry_run_true(self):
        ctx = _ctx(dry_run=True)
        result = guard_dry_run_enabled(ctx)
        assert result.passed is True

    def test_blocked_when_dry_run_false(self):
        ctx = _ctx(dry_run=False)
        result = guard_dry_run_enabled(ctx)
        assert result.passed is False
        assert result.severity == "blocked"


class TestOrgGuard:
    def test_passes_same_org(self):
        org = uuid.uuid4()
        ctx = _ctx(org_id=org, creative_org_id=org)
        assert guard_creative_in_org(ctx).passed is True

    def test_blocked_different_org(self):
        ctx = _ctx(org_id=uuid.uuid4(), creative_org_id=uuid.uuid4())
        result = guard_creative_in_org(ctx)
        assert result.passed is False
        assert result.severity == "blocked"


class TestApprovalGuard:
    def test_passes_with_approval(self):
        ctx = _ctx(has_approval=True)
        assert guard_approval_present(ctx).passed is True

    def test_blocked_without_approval(self):
        ctx = _ctx(has_approval=False)
        result = guard_approval_present(ctx)
        assert result.passed is False

    def test_skipped_when_approval_not_required(self):
        ctx = _ctx(has_approval=False, require_human_approval=False)
        result = guard_approval_present(ctx)
        assert result.passed is True


class TestBlockedGuard:
    def test_blocked_quality_check(self):
        ctx = _ctx(has_blocked_quality_check=True)
        result = guard_not_blocked(ctx)
        assert result.passed is False
        assert "quality" in result.code

    def test_blocked_policy_check(self):
        ctx = _ctx(has_blocked_policy_check=True)
        result = guard_not_blocked(ctx)
        assert result.passed is False
        assert "policy" in result.code

    def test_passes_clean(self):
        ctx = _ctx(has_blocked_quality_check=False, has_blocked_policy_check=False)
        assert guard_not_blocked(ctx).passed is True


class TestCreativeStatusGuard:
    def test_approved_passes(self):
        ctx = _ctx(creative_status="approved")
        assert guard_creative_status(ctx).passed is True

    def test_awaiting_approval_passes(self):
        ctx = _ctx(creative_status="awaiting_approval")
        assert guard_creative_status(ctx).passed is True

    def test_rejected_blocked(self):
        ctx = _ctx(creative_status="rejected")
        result = guard_creative_status(ctx)
        assert result.passed is False

    def test_queued_blocked(self):
        ctx = _ctx(creative_status="queued")
        assert guard_creative_status(ctx).passed is False


class TestRbacGuard:
    def test_owner_passes(self):
        assert guard_rbac(_ctx(actor_role="owner")).passed is True

    def test_admin_passes(self):
        assert guard_rbac(_ctx(actor_role="admin")).passed is True

    def test_viewer_blocked(self):
        result = guard_rbac(_ctx(actor_role="viewer"))
        assert result.passed is False
        assert result.severity == "blocked"


class TestBudgetGuards:
    def test_missing_budget_blocked(self):
        result = guard_budget_present(_ctx(daily_budget_brl=None))
        assert result.passed is False

    def test_zero_budget_blocked(self):
        result = guard_budget_present(_ctx(daily_budget_brl=0))
        assert result.passed is False

    def test_max_spend_not_set_blocked(self):
        ctx = _ctx(max_daily_spend=None, daily_budget_brl=50.0)
        result = guard_daily_spend_limit(ctx)
        assert result.passed is False
        assert "MAX_DAILY_SPEND" in result.detail

    def test_exceeds_daily_spend_blocked(self):
        ctx = _ctx(daily_budget_brl=300.0, max_daily_spend=200.0)
        result = guard_daily_spend_limit(ctx)
        assert result.passed is False
        assert "exceeds" in result.detail

    def test_within_daily_spend_passes(self):
        ctx = _ctx(daily_budget_brl=100.0, max_daily_spend=200.0)
        assert guard_daily_spend_limit(ctx).passed is True


class TestDailyAdsCount:
    def test_at_limit_blocked(self):
        ctx = _ctx(daily_simulated_count=3, max_daily_new_ads=3)
        result = guard_daily_ads_count(ctx)
        assert result.passed is False

    def test_below_limit_passes(self):
        ctx = _ctx(daily_simulated_count=2, max_daily_new_ads=3)
        assert guard_daily_ads_count(ctx).passed is True


class TestLandingUrlGuard:
    def test_valid_https_passes(self):
        ctx = _ctx(landing_url="https://mystore.com/offer")
        assert guard_landing_url(ctx).passed is True

    def test_no_url_warning_not_blocked(self):
        ctx = _ctx(landing_url=None)
        result = guard_landing_url(ctx)
        assert result.passed is True
        assert result.severity == "warning"

    def test_private_ip_blocked(self):
        ctx = _ctx(landing_url="http://192.168.1.1/admin")
        result = guard_landing_url(ctx)
        assert result.passed is False
        assert "ssrf" in result.code.lower()

    def test_loopback_blocked(self):
        ctx = _ctx(landing_url="http://127.0.0.1/api")
        result = guard_landing_url(ctx)
        assert result.passed is False

    def test_metadata_blocked(self):
        ctx = _ctx(landing_url="http://169.254.169.254/latest/meta-data/")
        result = guard_landing_url(ctx)
        assert result.passed is False

    def test_http_scheme_passes(self):
        ctx = _ctx(landing_url="http://example.com/page")
        assert guard_landing_url(ctx).passed is True

    def test_ftp_scheme_blocked(self):
        ctx = _ctx(landing_url="ftp://files.example.com/data")
        result = guard_landing_url(ctx)
        assert result.passed is False


class TestIdempotencyGuard:
    def test_new_attempt_passes(self):
        ctx = _ctx(previous_attempt_id=None)
        result = guard_idempotency(ctx)
        assert result.passed is True
        assert result.code == "idempotency_new"

    def test_same_hash_safe_retry(self):
        prev_id = uuid.uuid4()
        ctx = _ctx(
            previous_attempt_id=prev_id,
            previous_payload_hash="abc123",
            current_payload_hash="abc123",
        )
        result = guard_idempotency(ctx)
        assert result.passed is True
        assert result.code == "idempotency_safe_retry"

    def test_different_hash_conflict(self):
        ctx = _ctx(
            previous_attempt_id=uuid.uuid4(),
            previous_payload_hash="abc123",
            current_payload_hash="def456",
        )
        result = guard_idempotency(ctx)
        assert result.passed is False
        assert result.code == "idempotency_conflict"
        assert result.severity == "blocked"


class TestRunAllGuards:
    def test_happy_path_all_pass(self):
        ctx = _ctx()
        results = run_all_guards(ctx)
        assert not has_blocking_failure(results)

    def test_unapproved_creative_fails(self):
        ctx = _ctx(has_approval=False)
        results = run_all_guards(ctx)
        assert has_blocking_failure(results)

    def test_blocked_creative_fails(self):
        ctx = _ctx(has_blocked_quality_check=True)
        results = run_all_guards(ctx)
        assert has_blocking_failure(results)

    def test_dry_run_false_fails_immediately(self):
        ctx = _ctx(dry_run=False)
        results = run_all_guards(ctx)
        assert has_blocking_failure(results)

    def test_safe_retry_detected(self):
        prev_id = uuid.uuid4()
        ctx = _ctx(
            previous_attempt_id=prev_id,
            previous_payload_hash="hash",
            current_payload_hash="hash",
        )
        results = run_all_guards(ctx)
        assert is_safe_retry(results)

    def test_results_to_dict(self):
        ctx = _ctx()
        results = run_all_guards(ctx)
        dicts = results_to_dict(results)
        assert all(isinstance(d, dict) for d in dicts)
        assert all("code" in d and "severity" in d and "passed" in d for d in dicts)
