"""
Metric aggregation for experiment variants.

Aggregates VariantPerformanceSnapshot rows into a single AggregatedMetrics object.
Uses sum-of-numerators / sum-of-denominators (not average-of-averages).
All nullable fields stay null when no data is available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.analytics_engine.stats import safe_mean, safe_sum, winsorize

METRIC_NAMES = (
    "impressions", "reach", "clicks", "link_clicks",
    "landing_page_views", "adds_to_cart", "initiate_checkout",
    "purchases", "leads", "spend", "purchase_value",
    "frequency", "ctr", "cpc", "cpm", "cost_per_result", "roas",
)


@dataclass
class AggregatedMetrics:
    variant_id: str
    snapshot_count: int = 0
    matured_snapshot_count: int = 0

    # Summed metrics (additive)
    impressions: float | None = None
    reach: float | None = None
    clicks: float | None = None
    link_clicks: float | None = None
    landing_page_views: float | None = None
    adds_to_cart: float | None = None
    initiate_checkout: float | None = None
    purchases: float | None = None
    leads: float | None = None
    spend: float | None = None
    purchase_value: float | None = None

    # Derived rate metrics (recomputed from sums)
    frequency: float | None = None
    ctr: float | None = None
    cpc: float | None = None
    cpm: float | None = None
    cost_per_result: float | None = None
    roas: float | None = None

    limitations: list[str] = field(default_factory=list)
    outliers_detected: bool = False


def aggregate_variant_metrics(
    snapshots: list[Any],
    matured_only: bool = True,
    winsorize_roas: bool = True,
) -> AggregatedMetrics:
    """
    Aggregate a list of VariantPerformanceSnapshot ORM objects (or dicts) into
    a single AggregatedMetrics.

    matured_only=True skips snapshots where is_matured=False.
    """
    if not snapshots:
        return AggregatedMetrics(variant_id="unknown", snapshot_count=0)

    # Detect variant_id from first snapshot
    first = snapshots[0]
    variant_id = str(_get(first, "variant_id", "unknown"))

    agg = AggregatedMetrics(variant_id=variant_id, snapshot_count=len(snapshots))

    if matured_only:
        working = [s for s in snapshots if _get(s, "is_matured", True)]
        agg.matured_snapshot_count = len(working)
        if not working:
            agg.limitations.append("no_matured_snapshots")
            return agg
    else:
        working = list(snapshots)
        agg.matured_snapshot_count = len(working)

    # Additive metrics — collect non-null values then sum
    def _collect(field_name: str) -> list[float]:
        return [float(_get(s, field_name)) for s in working if _get(s, field_name) is not None]

    imp_vals = _collect("impressions")
    reach_vals = _collect("reach")
    click_vals = _collect("clicks")
    link_click_vals = _collect("link_clicks")
    lpv_vals = _collect("landing_page_views")
    cart_vals = _collect("adds_to_cart")
    checkout_vals = _collect("initiate_checkout")
    purchase_vals = _collect("purchases")
    lead_vals = _collect("leads")
    spend_vals = _collect("spend")
    pv_vals = _collect("purchase_value")
    roas_raw = _collect("roas")

    agg.impressions = safe_sum(imp_vals)
    agg.reach = safe_sum(reach_vals)
    agg.clicks = safe_sum(click_vals)
    agg.link_clicks = safe_sum(link_click_vals)
    agg.landing_page_views = safe_sum(lpv_vals)
    agg.adds_to_cart = safe_sum(cart_vals)
    agg.initiate_checkout = safe_sum(checkout_vals)
    agg.purchases = safe_sum(purchase_vals)
    agg.leads = safe_sum(lead_vals)
    agg.spend = safe_sum(spend_vals)
    agg.purchase_value = safe_sum(pv_vals)

    # Derived rates — from sums, not averages
    if agg.impressions and agg.reach and agg.reach > 0:
        agg.frequency = agg.impressions / agg.reach

    if agg.clicks is not None and agg.impressions and agg.impressions > 0:
        agg.ctr = (agg.clicks / agg.impressions) * 100.0

    if agg.spend is not None and agg.clicks and agg.clicks > 0:
        agg.cpc = agg.spend / agg.clicks

    if agg.spend is not None and agg.impressions and agg.impressions > 0:
        agg.cpm = (agg.spend / agg.impressions) * 1000.0

    # cost_per_result — use purchases then leads
    results = agg.purchases if agg.purchases is not None else agg.leads
    if agg.spend is not None and results and results > 0:
        agg.cost_per_result = agg.spend / results

    # ROAS — prefer reported, then derived from purchase_value/spend
    if roas_raw:
        if winsorize_roas and len(roas_raw) >= 3:
            roas_w = winsorize(roas_raw)
            if max(roas_raw) > 10 * min(r for r in roas_raw if r > 0):
                agg.outliers_detected = True
                agg.limitations.append("roas_outliers_winsorized")
            agg.roas = safe_mean(roas_w)
        else:
            agg.roas = safe_mean(roas_raw)
    elif agg.purchase_value is not None and agg.spend and agg.spend > 0:
        agg.roas = agg.purchase_value / agg.spend

    # Missing metric warnings
    if agg.impressions is None:
        agg.limitations.append("impressions_missing")
    if agg.spend is None:
        agg.limitations.append("spend_missing")

    return agg


def _get(obj: Any, attr: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
