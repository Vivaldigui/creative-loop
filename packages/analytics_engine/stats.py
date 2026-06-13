"""
Conservative statistical helpers for experiment evaluation.

Uses Beta-Binomial posterior for rate comparisons (CTR, CVR, etc.)
and bootstrap-style range for continuous metrics (ROAS, CPA).

No scipy dependency — implemented via math.lgamma.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

# ── Beta-Binomial (posterior) ─────────────────────────────────────────────────

def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _beta_cdf_regularized(x: float, a: float, b: float, steps: int = 200) -> float:
    """
    Numerical approximation of the regularized incomplete beta function I_x(a,b).
    Uses the continued-fraction method (Lentz) for x <= (a+1)/(a+b+2), otherwise
    uses the symmetry relation.  Accurate to ~4 decimal places for moderate a,b.
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    # Use symmetry to keep x on the convergent side
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _beta_cdf_regularized(1.0 - x, b, a, steps)

    lbeta_ab = _log_beta(a, b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta_ab) / a

    # Lentz continued-fraction
    TINY = 1e-30
    f = TINY
    C = f
    D = 0.0
    for m in range(steps):
        for e in (0, 1):
            if m == 0 and e == 0:
                d = 1.0
            elif e == 0:
                d = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                d = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
            D = 1.0 + d * D
            if abs(D) < TINY:
                D = TINY
            D = 1.0 / D
            C = 1.0 + d / C
            if abs(C) < TINY:
                C = TINY
            f *= C * D
            if abs(C * D - 1.0) < 1e-7:
                break

    return front * f


def beta_binomial_confidence(
    successes_b: int,
    trials_b: int,
    successes_a: int,
    trials_a: int,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
) -> float:
    """
    P(variant_b > variant_a) using Beta posterior with uniform prior (Laplace succession).

    Returns a value in [0, 1].  0.5 = no evidence of difference.
    Uses numerical integration over P(p_b > p_a) = ∫ Beta(a_B|…) * I(a_B) d(a_B).

    Conservative: uses add-1 Laplace prior to avoid zero-count posteriors.
    """
    # Posterior parameters
    alpha_a = prior_alpha + successes_a
    beta_a = prior_beta + (trials_a - successes_a)
    alpha_b = prior_alpha + successes_b
    beta_b = prior_beta + (trials_b - successes_b)

    # Numerical integration: P(p_b > p_a) = sum over grid of p_b
    n_steps = 300
    result = 0.0
    # We approximate ∫₀¹ Beta(p_b; alpha_b, beta_b) * I_{p_b}(alpha_a, beta_a) d(p_b)
    # which equals the probability that a draw from Beta_b > a draw from Beta_a
    dp = 1.0 / n_steps
    # Use midpoints
    for i in range(n_steps):
        p_b = (i + 0.5) * dp
        # PDF of p_b under posterior B (unnormalized — normalise by beta function)
        log_pdf_b = (alpha_b - 1) * math.log(p_b + 1e-300) + (beta_b - 1) * math.log(1 - p_b + 1e-300)
        pdf_b = math.exp(log_pdf_b - _log_beta(alpha_b, beta_b))
        # CDF of A at p_b = P(p_a < p_b)
        cdf_a = _beta_cdf_regularized(p_b, alpha_a, beta_a)
        result += pdf_b * cdf_a * dp

    return max(0.0, min(1.0, result))


# ── Continuous metric helpers ─────────────────────────────────────────────────

def relative_difference(value_test: float, value_control: float) -> float | None:
    """(test - control) / control.  Returns None if control is zero or None."""
    if value_control is None or value_test is None:
        return None
    if abs(value_control) < 1e-9:
        return None
    return (value_test - value_control) / abs(value_control)


def winsorize(values: Sequence[float], lower_pct: float = 0.05, upper_pct: float = 0.95) -> list[float]:
    """Clip values to [lower_pct, upper_pct] quantiles."""
    if not values:
        return []
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    lo_idx = max(0, int(math.floor(lower_pct * n)))
    hi_idx = min(n - 1, int(math.ceil(upper_pct * n)) - 1)
    lo = sorted_vals[lo_idx]
    hi = sorted_vals[hi_idx]
    return [max(lo, min(hi, v)) for v in values]


def safe_mean(values: Sequence[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def safe_sum(values: Sequence[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean)
