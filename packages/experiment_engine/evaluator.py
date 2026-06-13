"""
Conservative experiment evaluator.

evaluate_experiment() is a pure function — no DB access.
All inputs are plain dicts/dataclasses; result is EvaluationResult.

Evaluation states:
    insufficient_data   — minimum criteria not met at all
    collecting          — some criteria met but not all
    inconclusive        — sufficient data but no clear direction
    promising           — positive direction, not yet winner threshold
    underperforming     — negative direction consistent
    winner_candidate    — ALL minimum criteria met + diff >= min_diff + conf >= min_conf
    completed           — experiment manually completed
    stopped_for_safety  — stopped due to safety signal

EXPLORATORY mode:
    - causal_attribution = False always
    - maximum state = promising (never winner_candidate)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.analytics_engine.aggregator import AggregatedMetrics, aggregate_variant_metrics
from packages.analytics_engine.stats import beta_binomial_confidence, relative_difference

ENGINE_VERSION = "1.0.0"

# Metrics that can use Beta-Binomial (rate = successes/trials)
_RATE_METRICS = {"ctr", "cvr", "purchase_rate", "lead_rate"}
# Metrics where LOWER is better
_LOWER_IS_BETTER = {"cpc", "cpm", "cost_per_result"}


@dataclass
class VariantResult:
    variant_id: str
    is_control: bool
    metric_value: float | None
    relative_diff: float | None  # vs. control; None for control
    confidence: float | None     # P(test > control) for rates; None for control
    aggregated: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    evaluation_state: str
    primary_metric: str | None
    variant_results: list[VariantResult]
    confidence: float | None  # max across test variants
    data_window: dict[str, Any]
    limitations: list[str]
    causal_attribution: bool
    engine_version: str = ENGINE_VERSION
    notes: str = ""


def evaluate_experiment(
    mode: str,
    primary_metric: str,
    variants: list[dict[str, Any]],
    snapshots_by_variant: dict[str, list[Any]],
    min_criteria: dict[str, Any] | None = None,
) -> EvaluationResult:
    """
    Pure evaluation function.

    variants: list of dicts with keys: id, is_control, name
    snapshots_by_variant: { variant_id: [snapshot_orm_or_dict, ...] }
    min_criteria: { min_spend, min_impressions, min_clicks, min_conversions,
                    min_days, min_difference, min_confidence, max_frequency,
                    maturation_window_days }
    """
    criteria = _defaults(min_criteria or {})
    limitations: list[str] = []
    causal = (mode == "CONTROLLED")

    # ── Aggregate metrics per variant ─────────────────────────────────────────
    agg_by_variant: dict[str, AggregatedMetrics] = {}
    for v in variants:
        vid = str(v["id"])
        snaps = snapshots_by_variant.get(vid, [])
        agg = aggregate_variant_metrics(snaps, matured_only=True)
        agg_by_variant[vid] = agg
        limitations.extend(f"variant_{vid[:8]}: {lim}" for lim in agg.limitations)

    # ── Identify control and test variants ───────────────────────────────────
    control_variant = next((v for v in variants if v.get("is_control")), None)
    test_variants = [v for v in variants if not v.get("is_control")]

    if not control_variant:
        limitations.append("no_control_variant")
        return EvaluationResult(
            evaluation_state="insufficient_data",
            primary_metric=primary_metric,
            variant_results=[],
            confidence=None,
            data_window={},
            limitations=limitations,
            causal_attribution=False,
            notes="No control variant found.",
        )

    ctrl_id = str(control_variant["id"])
    ctrl_agg = agg_by_variant.get(ctrl_id, AggregatedMetrics(variant_id=ctrl_id))

    # ── Check minimum data criteria ──────────────────────────────────────────
    sufficiency_issues = _check_sufficiency(ctrl_agg, criteria, limitations)
    for v in test_variants:
        vid = str(v["id"])
        sufficiency_issues += _check_sufficiency(agg_by_variant.get(vid, AggregatedMetrics(variant_id=vid)), criteria, limitations)

    # ── Build data window ────────────────────────────────────────────────────
    all_aggs = list(agg_by_variant.values())
    total_snaps = sum(a.matured_snapshot_count for a in all_aggs)
    data_window = {
        "total_matured_snapshots": total_snaps,
        "min_spend_required": criteria["min_spend"],
        "control_spend": ctrl_agg.spend,
    }

    if sufficiency_issues > 0:
        state = "insufficient_data" if sufficiency_issues > 2 else "collecting"
        return EvaluationResult(
            evaluation_state=state,
            primary_metric=primary_metric,
            variant_results=_build_results(ctrl_id, test_variants, agg_by_variant, primary_metric, criteria),
            confidence=None,
            data_window=data_window,
            limitations=limitations,
            causal_attribution=False,
            notes=f"{sufficiency_issues} sufficiency criteria not met.",
        )

    # ── Frequency check (fatigue) ─────────────────────────────────────────────
    max_freq = criteria.get("max_frequency")
    if max_freq:
        for v in variants:
            vid = str(v["id"])
            agg = agg_by_variant.get(vid)
            if agg and agg.frequency and agg.frequency > max_freq:
                limitations.append(f"variant_{vid[:8]}_frequency_high ({agg.frequency:.1f} > {max_freq})")

    # ── Compute variant results ────────────────────────────────────────────────
    variant_results = _build_results(ctrl_id, test_variants, agg_by_variant, primary_metric, criteria)

    # ── Determine overall state ───────────────────────────────────────────────
    test_results = [r for r in variant_results if not r.is_control]
    confidences = [r.confidence for r in test_results if r.confidence is not None]
    diffs = [r.relative_diff for r in test_results if r.relative_diff is not None]

    max_confidence = max(confidences) if confidences else None
    min_diff_threshold = criteria["min_difference"]
    min_conf_threshold = criteria["min_confidence"]

    # Peeking warning
    limitations.append("peeking_risk: evaluate at fixed intervals only; repeated checking inflates false-positive rate")

    if not diffs:
        state = "inconclusive"
    else:
        positive_diffs = [d for d in diffs if d > 0]  # noqa: F841
        negative_diffs = [d for d in diffs if d < 0]  # noqa: F841

        best_diff = max(diffs) if not _is_lower_better(primary_metric) else -min(diffs)

        if best_diff >= min_diff_threshold and max_confidence and max_confidence >= min_conf_threshold:
            if mode == "CONTROLLED":
                state = "winner_candidate"
            else:
                # EXPLORATORY never reaches winner_candidate
                state = "promising"
                limitations.append("exploratory_no_causation: EXPLORATORY mode cannot attribute causality to single variable")
        elif best_diff >= min_diff_threshold * 0.5 and max_confidence and max_confidence >= 0.6:
            state = "promising"
        elif len(negative_diffs) == len(diffs) and all(abs(d) >= min_diff_threshold * 0.5 for d in negative_diffs):
            state = "underperforming"
        else:
            state = "inconclusive"

    return EvaluationResult(
        evaluation_state=state,
        primary_metric=primary_metric,
        variant_results=variant_results,
        confidence=max_confidence,
        data_window=data_window,
        limitations=limitations,
        causal_attribution=causal and state == "winner_candidate",
        engine_version=ENGINE_VERSION,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _defaults(criteria: dict[str, Any]) -> dict[str, Any]:
    return {
        "min_spend": criteria.get("min_spend", 50.0),
        "min_impressions": criteria.get("min_impressions", 1000),
        "min_clicks": criteria.get("min_clicks", 50),
        "min_conversions": criteria.get("min_conversions", 0),
        "min_days": criteria.get("min_days", 3),
        "min_difference": criteria.get("min_difference", 0.10),
        "min_confidence": criteria.get("min_confidence", 0.80),
        "max_frequency": criteria.get("max_frequency", 4.0),
        "maturation_window_days": criteria.get("maturation_window_days", 3),
    }


def _check_sufficiency(agg: AggregatedMetrics, criteria: dict[str, Any], limitations: list[str]) -> int:
    issues = 0
    vid = agg.variant_id[:8]
    if criteria["min_spend"] and (agg.spend is None or agg.spend < criteria["min_spend"]):
        limitations.append(f"variant_{vid}_spend_below_minimum")
        issues += 1
    if criteria["min_impressions"] and (agg.impressions is None or agg.impressions < criteria["min_impressions"]):
        limitations.append(f"variant_{vid}_impressions_below_minimum")
        issues += 1
    if criteria["min_clicks"] and (agg.clicks is None or agg.clicks < criteria["min_clicks"]):
        limitations.append(f"variant_{vid}_clicks_below_minimum")
        issues += 1
    if agg.matured_snapshot_count == 0:
        limitations.append(f"variant_{vid}_no_matured_data")
        issues += 1
    return issues


def _build_results(
    ctrl_id: str,
    test_variants: list[dict[str, Any]],
    agg_by_variant: dict[str, AggregatedMetrics],
    primary_metric: str,
    criteria: dict[str, Any],
) -> list[VariantResult]:
    results = []
    ctrl_agg = agg_by_variant.get(ctrl_id, AggregatedMetrics(variant_id=ctrl_id))
    ctrl_val = _get_metric(ctrl_agg, primary_metric)

    results.append(VariantResult(
        variant_id=ctrl_id,
        is_control=True,
        metric_value=ctrl_val,
        relative_diff=None,
        confidence=None,
        aggregated=_agg_dict(ctrl_agg),
    ))

    for v in test_variants:
        vid = str(v["id"])
        agg = agg_by_variant.get(vid, AggregatedMetrics(variant_id=vid))
        test_val = _get_metric(agg, primary_metric)

        rel_diff = relative_difference(test_val, ctrl_val) if (test_val is not None and ctrl_val is not None) else None

        # For lower-is-better metrics, flip sign so positive = improvement
        if rel_diff is not None and _is_lower_better(primary_metric):
            rel_diff = -rel_diff

        confidence = _compute_confidence(agg, ctrl_agg, primary_metric)

        results.append(VariantResult(
            variant_id=vid,
            is_control=False,
            metric_value=test_val,
            relative_diff=rel_diff,
            confidence=confidence,
            aggregated=_agg_dict(agg),
        ))

    return results


def _get_metric(agg: AggregatedMetrics, metric: str) -> float | None:
    return getattr(agg, metric, None)


def _is_lower_better(metric: str) -> bool:
    return metric in _LOWER_IS_BETTER


def _compute_confidence(test_agg: AggregatedMetrics, ctrl_agg: AggregatedMetrics, metric: str) -> float | None:
    """Use Beta-Binomial for rate metrics; return None for continuous without sufficient data."""
    if metric == "ctr":
        # successes = clicks, trials = impressions
        s_b = int(test_agg.clicks or 0)
        t_b = int(test_agg.impressions or 0)
        s_a = int(ctrl_agg.clicks or 0)
        t_a = int(ctrl_agg.impressions or 0)
        if t_b < 10 or t_a < 10:
            return None
        return beta_binomial_confidence(s_b, t_b, s_a, t_a)

    if metric in ("purchases", "leads", "purchase_rate", "cvr"):
        # successes = conversions, trials = clicks
        s_b = int(test_agg.purchases or test_agg.leads or 0)
        t_b = int(test_agg.clicks or 0)
        s_a = int(ctrl_agg.purchases or ctrl_agg.leads or 0)
        t_a = int(ctrl_agg.clicks or 0)
        if t_b < 10 or t_a < 10:
            return None
        return beta_binomial_confidence(s_b, t_b, s_a, t_a)

    # Continuous metrics (ROAS, CPA, etc.) — no distribution assumed; return None
    return None


def _agg_dict(agg: AggregatedMetrics) -> dict[str, Any]:
    return {
        "impressions": agg.impressions,
        "clicks": agg.clicks,
        "spend": agg.spend,
        "purchases": agg.purchases,
        "leads": agg.leads,
        "ctr": agg.ctr,
        "cpc": agg.cpc,
        "roas": agg.roas,
        "cost_per_result": agg.cost_per_result,
        "purchase_value": agg.purchase_value,
        "frequency": agg.frequency,
        "matured_snapshot_count": agg.matured_snapshot_count,
    }
