"""
Publication guards — pure validation functions.

Each guard returns a CheckResult. Guards are run in order before any
simulation is attempted. All guards must pass (no BLOCKED results) for
the simulation to proceed.

Guards are pure functions (no DB side-effects). The service layer calls
them and persists the results.
"""
from __future__ import annotations

import ipaddress
import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass
class CheckResult:
    code: str
    severity: str  # "pass" | "warning" | "blocked"
    passed: bool
    detail: str = ""


@dataclass
class GuardContext:
    """All data needed to run every guard — assembled once, passed to each check."""

    # Identity
    actor_role: str
    org_id: uuid.UUID

    # Creative state
    creative_org_id: uuid.UUID
    creative_status: str
    creative_id: uuid.UUID
    has_approval: bool
    approval_id: uuid.UUID | None
    has_blocked_quality_check: bool
    has_blocked_policy_check: bool

    # Budget
    daily_budget_brl: float | None   # in main currency unit (BRL), not centavos
    max_daily_spend: float | None
    max_experiment_budget: float | None
    experiment_id: uuid.UUID | None
    experiment_budget_used: float    # sum of approved/simulated attempts this experiment

    # Daily count
    daily_simulated_count: int
    max_daily_new_ads: int

    # Landing page
    landing_url: str | None

    # Minimum config (campaign / adset)
    objective: str | None
    optimization_goal: str | None
    has_page_reference: bool          # page_id not a placeholder

    # Idempotency (resolved before guard run)
    idempotency_key: str
    previous_attempt_id: uuid.UUID | None
    previous_payload_hash: str | None
    current_payload_hash: str
    idempotency_ttl_hours: int = 24

    # Guard settings
    require_human_approval: bool = True
    dry_run: bool = True

    # Phase 6 — real-mode flags
    meta_write_enabled: bool = False
    credentials_valid: bool = False   # result of health-check (pre-resolved by caller)
    audit_available: bool = True      # sanity: audit subsystem is writable

    # Extra metadata for limits_checked snapshot
    extra: dict[str, Any] = field(default_factory=dict)


# ── Individual guards (each returns CheckResult) ──────────────────────────────

def guard_dry_run_enabled(ctx: GuardContext) -> CheckResult:
    if not ctx.dry_run:
        return CheckResult(
            code="dry_run_disabled",
            severity="blocked",
            passed=False,
            detail="DRY_RUN=false: this endpoint only operates in DRY_RUN mode.",
        )
    return CheckResult(code="dry_run_enabled", severity="pass", passed=True)


# ── Real-mode guards (only evaluated when mode="real") ────────────────────────

def guard_real_mode_enabled(ctx: GuardContext) -> CheckResult:
    """Inverse of guard_dry_run_enabled: require DRY_RUN=false for real publish."""
    if ctx.dry_run:
        return CheckResult(
            code="real_mode_blocked_dry_run",
            severity="blocked",
            passed=False,
            detail="DRY_RUN=true — real publish is disabled. Set DRY_RUN=false to enable.",
        )
    return CheckResult(code="real_mode_enabled", severity="pass", passed=True)


def guard_write_enabled(ctx: GuardContext) -> CheckResult:
    """Require META_WRITE_ENABLED=true (second safety interlock independent of DRY_RUN)."""
    if not ctx.meta_write_enabled:
        return CheckResult(
            code="write_not_enabled",
            severity="blocked",
            passed=False,
            detail=(
                "META_WRITE_ENABLED=false — real publish is disabled. "
                "Set META_WRITE_ENABLED=true in .env to enable real Meta writes."
            ),
        )
    return CheckResult(code="write_enabled", severity="pass", passed=True)


def guard_credentials_valid(ctx: GuardContext) -> CheckResult:
    """Require that the Meta write token health-check passed."""
    if not ctx.credentials_valid:
        return CheckResult(
            code="credentials_invalid",
            severity="blocked",
            passed=False,
            detail=(
                "Meta credentials are invalid, expired, or have insufficient scopes. "
                "Check META_ACCESS_TOKEN and re-run POST /integrations/meta/test."
            ),
        )
    return CheckResult(code="credentials_valid", severity="pass", passed=True)


def guard_audit_available(ctx: GuardContext) -> CheckResult:
    """Sanity guard: audit subsystem must be available. Fail-closed."""
    if not ctx.audit_available:
        return CheckResult(
            code="audit_unavailable",
            severity="blocked",
            passed=False,
            detail=(
                "AuditLog subsystem is not available. "
                "Real publish is blocked until audit logging is operational."
            ),
        )
    return CheckResult(code="audit_available", severity="pass", passed=True)


def guard_creative_in_org(ctx: GuardContext) -> CheckResult:
    if ctx.creative_org_id != ctx.org_id:
        return CheckResult(
            code="creative_not_in_org",
            severity="blocked",
            passed=False,
            detail="Creative does not belong to this organisation.",
        )
    return CheckResult(code="creative_in_org", severity="pass", passed=True)


def guard_approval_present(ctx: GuardContext) -> CheckResult:
    if not ctx.require_human_approval:
        return CheckResult(
            code="approval_not_required",
            severity="pass",
            passed=True,
            detail="REQUIRE_HUMAN_APPROVAL=false — approval check skipped.",
        )
    if not ctx.has_approval:
        return CheckResult(
            code="approval_missing",
            severity="blocked",
            passed=False,
            detail="Creative must be approved by a human before simulating publication.",
        )
    return CheckResult(code="approval_present", severity="pass", passed=True)


def guard_not_blocked(ctx: GuardContext) -> CheckResult:
    if ctx.has_blocked_quality_check:
        return CheckResult(
            code="quality_check_blocked",
            severity="blocked",
            passed=False,
            detail="Creative has a BLOCKED quality check and cannot be published.",
        )
    if ctx.has_blocked_policy_check:
        return CheckResult(
            code="policy_check_blocked",
            severity="blocked",
            passed=False,
            detail="Creative has a BLOCKED policy check and cannot be published.",
        )
    return CheckResult(code="not_blocked", severity="pass", passed=True)


def guard_creative_status(ctx: GuardContext) -> CheckResult:
    publishable = {"approved", "awaiting_approval"}
    if ctx.creative_status not in publishable:
        return CheckResult(
            code="creative_status_not_publishable",
            severity="blocked",
            passed=False,
            detail=f"Creative status '{ctx.creative_status}' cannot be published. Required: {sorted(publishable)}.",
        )
    return CheckResult(code="creative_status_ok", severity="pass", passed=True)


def guard_rbac(ctx: GuardContext) -> CheckResult:
    if ctx.actor_role not in ("owner", "admin"):
        return CheckResult(
            code="rbac_insufficient_role",
            severity="blocked",
            passed=False,
            detail=f"Role '{ctx.actor_role}' cannot simulate publication. Required: owner or admin.",
        )
    return CheckResult(code="rbac_ok", severity="pass", passed=True)


def guard_budget_present(ctx: GuardContext) -> CheckResult:
    if ctx.daily_budget_brl is None or ctx.daily_budget_brl <= 0:
        return CheckResult(
            code="budget_missing",
            severity="blocked",
            passed=False,
            detail="daily_budget must be provided and greater than zero.",
        )
    return CheckResult(code="budget_present", severity="pass", passed=True)


def guard_daily_spend_limit(ctx: GuardContext) -> CheckResult:
    if ctx.max_daily_spend is None:
        return CheckResult(
            code="max_daily_spend_not_set",
            severity="blocked",
            passed=False,
            detail=(
                "MAX_DAILY_SPEND is not configured. "
                "Set it in .env before simulating publication."
            ),
        )
    budget = ctx.daily_budget_brl or 0.0
    if budget > ctx.max_daily_spend:
        return CheckResult(
            code="daily_spend_limit_exceeded",
            severity="blocked",
            passed=False,
            detail=(
                f"daily_budget {budget:.2f} exceeds MAX_DAILY_SPEND {ctx.max_daily_spend:.2f}."
            ),
        )
    return CheckResult(
        code="daily_spend_limit_ok",
        severity="pass",
        passed=True,
        detail=f"Budget {budget:.2f} ≤ limit {ctx.max_daily_spend:.2f}.",
    )


def guard_experiment_budget(ctx: GuardContext) -> CheckResult:
    if ctx.experiment_id is None:
        return CheckResult(code="experiment_budget_na", severity="pass", passed=True)
    if ctx.max_experiment_budget is None:
        return CheckResult(
            code="max_experiment_budget_not_set",
            severity="warning",
            passed=True,
            detail="MAX_EXPERIMENT_BUDGET not set — no experiment-level cap enforced.",
        )
    budget = ctx.daily_budget_brl or 0.0
    projected = ctx.experiment_budget_used + budget
    if projected > ctx.max_experiment_budget:
        return CheckResult(
            code="experiment_budget_exceeded",
            severity="blocked",
            passed=False,
            detail=(
                f"Adding {budget:.2f} would bring experiment total to "
                f"{projected:.2f}, exceeding MAX_EXPERIMENT_BUDGET {ctx.max_experiment_budget:.2f}."
            ),
        )
    return CheckResult(
        code="experiment_budget_ok",
        severity="pass",
        passed=True,
        detail=f"Experiment budget used {ctx.experiment_budget_used:.2f} + {budget:.2f} ≤ {ctx.max_experiment_budget:.2f}.",
    )


def guard_daily_ads_count(ctx: GuardContext) -> CheckResult:
    if ctx.daily_simulated_count >= ctx.max_daily_new_ads:
        return CheckResult(
            code="daily_ads_count_exceeded",
            severity="blocked",
            passed=False,
            detail=(
                f"Already simulated {ctx.daily_simulated_count} ads today "
                f"(limit: {ctx.max_daily_new_ads})."
            ),
        )
    return CheckResult(
        code="daily_ads_count_ok",
        severity="pass",
        passed=True,
        detail=f"{ctx.daily_simulated_count}/{ctx.max_daily_new_ads} simulations used today.",
    )


def guard_landing_url(ctx: GuardContext) -> CheckResult:
    url = ctx.landing_url
    if not url:
        if not ctx.dry_run:
            return CheckResult(
                code="landing_url_missing",
                severity="blocked",
                passed=False,
                detail="Landing URL is required for real Meta publish.",
            )
        return CheckResult(
            code="landing_url_missing",
            severity="warning",
            passed=True,
            detail="No landing URL provided — required for real publish.",
        )
    try:
        parsed = urlparse(url)
    except Exception:
        return CheckResult(
            code="landing_url_invalid",
            severity="blocked",
            passed=False,
            detail="Landing URL could not be parsed.",
        )

    if parsed.scheme not in ("http", "https"):
        return CheckResult(
            code="landing_url_scheme_invalid",
            severity="blocked",
            passed=False,
            detail=f"Landing URL must use http or https, got '{parsed.scheme}'.",
        )

    hostname = parsed.hostname or ""
    if _is_ssrf_risk(hostname):
        return CheckResult(
            code="landing_url_ssrf_risk",
            severity="blocked",
            passed=False,
            detail=f"Landing URL hostname '{hostname}' resolves to a private/reserved address (SSRF risk).",
        )

    return CheckResult(code="landing_url_ok", severity="pass", passed=True)


def guard_min_config(ctx: GuardContext) -> CheckResult:
    issues: list[str] = []
    if not ctx.objective:
        issues.append("campaign objective missing")
    if not ctx.optimization_goal:
        issues.append("adset optimization_goal missing")
    if not ctx.has_page_reference:
        issues.append("Meta Page ID is a placeholder (PENDING_META_PAGE_ID)")

    if issues:
        # In DRY_RUN: warnings only.  In real mode: hard block.
        if not ctx.dry_run:
            return CheckResult(
                code="min_config_missing",
                severity="blocked",
                passed=False,
                detail=f"Configuration incomplete for real publish: {'; '.join(issues)}.",
            )
        return CheckResult(
            code="min_config_warnings",
            severity="warning",
            passed=True,
            detail=f"Configuration warnings (block real publish): {'; '.join(issues)}.",
        )
    return CheckResult(code="min_config_ok", severity="pass", passed=True)


def guard_idempotency(ctx: GuardContext) -> CheckResult:
    if ctx.previous_attempt_id is None:
        return CheckResult(code="idempotency_new", severity="pass", passed=True, detail="New attempt.")

    # Same key + same payload → safe retry
    if ctx.previous_payload_hash == ctx.current_payload_hash:
        return CheckResult(
            code="idempotency_safe_retry",
            severity="pass",
            passed=True,
            detail=f"Same payload hash — returning existing attempt {ctx.previous_attempt_id}.",
        )

    # Same key + different payload → conflict
    return CheckResult(
        code="idempotency_conflict",
        severity="blocked",
        passed=False,
        detail=(
            f"Idempotency key '{ctx.idempotency_key}' was already used with a different payload. "
            "Use a new idempotency key or resubmit with the identical payload."
        ),
    )


# ── Guard sequences ───────────────────────────────────────────────────────────

# DRY_RUN mode: first guard asserts DRY_RUN=true; real-mode guards not run
_DRY_RUN_GUARD_SEQUENCE = [
    guard_dry_run_enabled,
    guard_creative_in_org,
    guard_approval_present,
    guard_not_blocked,
    guard_creative_status,
    guard_rbac,
    guard_budget_present,
    guard_daily_spend_limit,
    guard_experiment_budget,
    guard_daily_ads_count,
    guard_landing_url,
    guard_min_config,
    guard_idempotency,
]

# REAL mode: DRY_RUN guard is replaced by real-mode gates; min_config & landing_url become hard blocks
_REAL_GUARD_SEQUENCE = [
    guard_real_mode_enabled,
    guard_write_enabled,
    guard_credentials_valid,
    guard_audit_available,
    guard_creative_in_org,
    guard_approval_present,
    guard_not_blocked,
    guard_creative_status,
    guard_rbac,
    guard_budget_present,
    guard_daily_spend_limit,
    guard_experiment_budget,
    guard_daily_ads_count,
    guard_landing_url,      # blocks (not warns) when dry_run=False
    guard_min_config,       # blocks (not warns) when dry_run=False
    guard_idempotency,
]


def run_all_guards(ctx: GuardContext, mode: str = "dry_run") -> list[CheckResult]:
    """
    Execute guards for the given mode.

    mode="dry_run" — DRY_RUN sequence (guard_dry_run_enabled first).
    mode="real"    — Real-write sequence (real-mode gates first, stricter min_config).
    """
    sequence = _REAL_GUARD_SEQUENCE if mode == "real" else _DRY_RUN_GUARD_SEQUENCE
    results: list[CheckResult] = []
    for guard_fn in sequence:
        result = guard_fn(ctx)
        results.append(result)
    return results


def has_blocking_failure(results: list[CheckResult]) -> bool:
    """Return True if any guard produced a non-passed blocked result."""
    return any(not r.passed and r.severity == "blocked" for r in results)


def is_safe_retry(results: list[CheckResult]) -> bool:
    """Return True if the idempotency guard detected a safe retry (same payload)."""
    return any(r.code == "idempotency_safe_retry" for r in results)


def results_to_dict(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [
        {"code": r.code, "severity": r.severity, "passed": r.passed, "detail": r.detail}
        for r in results
    ]


# ── SSRF helpers ──────────────────────────────────────────────────────────────

_PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_METADATA_HOSTNAMES = re.compile(
    r"^(169\.254\.169\.254|metadata\.google\.internal|instance-data)$",
    re.IGNORECASE,
)


def _is_ssrf_risk(hostname: str) -> bool:
    if not hostname:
        return False
    if _METADATA_HOSTNAMES.match(hostname):
        return True
    try:
        addr = ipaddress.ip_address(hostname)
        return any(addr in net for net in _PRIVATE_IP_RANGES)
    except ValueError:
        # Not an IP — hostname, trust DNS resolution (don't block)
        return False
