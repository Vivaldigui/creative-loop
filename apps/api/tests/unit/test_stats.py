"""Unit tests for analytics_engine.stats — pure math, no I/O."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from packages.analytics_engine.stats import (
    beta_binomial_confidence,
    relative_difference,
    safe_mean,
    safe_sum,
    winsorize,
)


class TestBetaBinomialConfidence:
    def test_equal_rates_returns_near_50(self):
        p = beta_binomial_confidence(100, 1000, 100, 1000)
        assert 0.40 < p < 0.60

    def test_clearly_better_returns_high(self):
        # B: 200/1000 (20%), A: 100/1000 (10%)
        p = beta_binomial_confidence(200, 1000, 100, 1000)
        assert p > 0.90

    def test_clearly_worse_returns_low(self):
        # B: 50/1000 (5%), A: 150/1000 (15%)
        p = beta_binomial_confidence(50, 1000, 150, 1000)
        assert p < 0.20

    def test_zero_trials_returns_half(self):
        p = beta_binomial_confidence(0, 0, 0, 0)
        assert abs(p - 0.5) < 1e-9

    def test_zero_successes_returns_low(self):
        p = beta_binomial_confidence(0, 1000, 100, 1000)
        assert p < 0.10

    def test_result_is_probability(self):
        p = beta_binomial_confidence(80, 400, 60, 400)
        assert 0.0 <= p <= 1.0


class TestRelativeDifference:
    def test_basic(self):
        diff = relative_difference(1.1, 1.0)
        assert abs(diff - 0.1) < 1e-9

    def test_negative(self):
        diff = relative_difference(0.9, 1.0)
        assert abs(diff - (-0.1)) < 1e-9

    def test_zero_control_returns_none(self):
        assert relative_difference(1.0, 0.0) is None

    def test_near_zero_returns_none(self):
        assert relative_difference(1.0, 1e-15) is None

    def test_zero_test_with_nonzero_control(self):
        diff = relative_difference(0.0, 1.0)
        assert diff == -1.0


class TestWinsorize:
    def test_clips_outliers(self):
        # 20 values in [0,19] + clear outlier 1000 — 95th pct is ~19, so 1000 gets clipped
        vals = list(range(20)) + [1000]
        result = winsorize(vals, 0.05, 0.95)
        assert max(result) < 1000
        assert len(result) == len(vals)

    def test_no_change_when_within_bounds(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = winsorize(vals, 0.0, 1.0)
        assert result == vals

    def test_empty_list(self):
        assert winsorize([], 0.05, 0.95) == []

    def test_single_element(self):
        assert winsorize([5.0], 0.1, 0.9) == [5.0]


class TestSafeAggs:
    def test_safe_mean_basic(self):
        assert safe_mean([1.0, 2.0, 3.0]) == 2.0

    def test_safe_mean_empty(self):
        assert safe_mean([]) is None

    def test_safe_mean_none_values(self):
        assert safe_mean([None, None]) is None

    def test_safe_mean_mixed(self):
        result = safe_mean([2.0, None, 4.0])
        assert result == 3.0

    def test_safe_sum_basic(self):
        assert safe_sum([1.0, 2.0, 3.0]) == 6.0

    def test_safe_sum_none_values(self):
        # safe_sum returns None when all values are None (no data)
        assert safe_sum([None, None]) is None

    def test_safe_sum_empty(self):
        # safe_sum returns None for empty list (no data)
        assert safe_sum([]) is None
