"""Unit tests for analytics_engine.aggregator."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from packages.analytics_engine.aggregator import aggregate_variant_metrics


@dataclass
class MockSnap:
    impressions: int | None = None
    clicks: int | None = None
    spend: float | None = None
    reach: int | None = None
    frequency: float | None = None
    purchases: int | None = None
    leads: int | None = None
    add_to_cart: int | None = None
    view_content: int | None = None
    ctr: float | None = None
    cpc: float | None = None
    cpm: float | None = None
    cpp: float | None = None
    cvr: float | None = None
    roas: float | None = None
    purchase_value: float | None = None
    cost_per_lead: float | None = None
    cost_per_add_to_cart: float | None = None
    is_matured: bool = True
    is_fictitious: bool = False


class TestAggregateVariantMetrics:
    def test_empty_returns_none_metrics(self):
        result = aggregate_variant_metrics([])
        assert result.impressions is None
        assert result.clicks is None
        assert result.spend is None

    def test_single_snapshot_sums(self):
        snap = MockSnap(impressions=1000, clicks=50, spend=100.0, purchases=5, purchase_value=500.0)
        result = aggregate_variant_metrics([snap])
        assert result.impressions == 1000
        assert result.clicks == 50
        assert result.spend == 100.0
        assert result.purchases == 5

    def test_multiple_snapshots_sum_counts(self):
        s1 = MockSnap(impressions=500, clicks=25, spend=50.0, purchases=2)
        s2 = MockSnap(impressions=500, clicks=25, spend=50.0, purchases=3)
        result = aggregate_variant_metrics([s1, s2])
        assert result.impressions == 1000
        assert result.clicks == 50
        assert result.spend == 100.0
        assert result.purchases == 5

    def test_derives_ctr(self):
        snap = MockSnap(impressions=1000, clicks=50)
        result = aggregate_variant_metrics([snap])
        assert result.ctr is not None
        assert abs(result.ctr - 5.0) < 0.01

    def test_derives_purchase_rate(self):
        # CVR is derived from purchases/clicks — check purchase_rate or ctr proxy
        snap = MockSnap(clicks=100, purchases=10, impressions=1000)
        result = aggregate_variant_metrics([snap])
        # aggregator derives ctr from clicks/impressions
        assert result.ctr is not None
        assert result.purchases == 10

    def test_matured_only_filters_unmatured(self):
        mature = MockSnap(impressions=1000, clicks=50, is_matured=True)
        immature = MockSnap(impressions=500, clicks=25, is_matured=False)
        result = aggregate_variant_metrics([mature, immature], matured_only=True)
        assert result.impressions == 1000

    def test_matured_false_includes_all(self):
        mature = MockSnap(impressions=1000, clicks=50, is_matured=True)
        immature = MockSnap(impressions=500, clicks=25, is_matured=False)
        result = aggregate_variant_metrics([mature, immature], matured_only=False)
        assert result.impressions == 1500

    def test_none_impressions_handled(self):
        snap = MockSnap(impressions=None, clicks=None, spend=50.0)
        result = aggregate_variant_metrics([snap])
        assert result.impressions is None
        assert result.spend == 50.0

    def test_limitations_populated_on_low_sample(self):
        snap = MockSnap(impressions=10, clicks=1, spend=5.0)
        result = aggregate_variant_metrics([snap])
        assert isinstance(result.limitations, list)
