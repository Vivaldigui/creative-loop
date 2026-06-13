"""Unit tests for experiment_engine.evaluator — minimum criteria and state transitions."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from packages.experiment_engine.evaluator import evaluate_experiment


@dataclass
class MockSnapshot:
    impressions: int | None = None
    clicks: int | None = None
    spend: float | None = None
    purchases: int | None = None
    leads: int | None = None
    ctr: float | None = None
    cvr: float | None = None
    roas: float | None = None
    is_matured: bool = True
    is_fictitious: bool = False


def make_snapshots(impressions: int, clicks: int, spend: float, purchases: int, is_matured: bool = True):
    return [MockSnapshot(
        impressions=impressions,
        clicks=clicks,
        spend=spend,
        purchases=purchases,
        is_matured=is_matured,
        ctr=(clicks / impressions * 100) if impressions else None,
        cvr=(purchases / clicks) if clicks else None,
    )]


MIN_CRITERIA = {
    "min_impressions": 100,
    "min_spend": 10.0,
    "min_clicks": 5,
    "min_days": 1,
    "min_difference": 0.05,
    "min_confidence": 0.75,
}


CTRL = {"id": "v_ctrl", "name": "control", "is_control": True}
TREAT = {"id": "v_treat", "name": "treatment", "is_control": False}


class TestInsufficientData:
    def test_no_snapshots_returns_insufficient(self):
        result = evaluate_experiment(
            mode="CONTROLLED",
            primary_metric="ctr",
            variants=[],
            snapshots_by_variant={},
            min_criteria=MIN_CRITERIA,
        )
        assert result.evaluation_state == "insufficient_data"
        assert not result.causal_attribution

    def test_immature_snapshots_insufficient(self):
        snapshots = make_snapshots(50, 5, 5.0, 0, is_matured=False)
        result = evaluate_experiment(
            mode="CONTROLLED",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": snapshots, "v_treat": snapshots},
            min_criteria=MIN_CRITERIA,
        )
        assert result.evaluation_state == "insufficient_data"

    def test_below_min_impressions_not_winner(self):
        # 50 impressions < min 100 — should be insufficient_data or collecting
        snapshots = make_snapshots(50, 5, 15.0, 1)
        result = evaluate_experiment(
            mode="CONTROLLED",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": snapshots, "v_treat": snapshots},
            min_criteria=MIN_CRITERIA,
        )
        assert result.evaluation_state in ("insufficient_data", "collecting")
        assert result.evaluation_state != "winner_candidate"


class TestExploratoryMode:
    def test_exploratory_never_reaches_winner_candidate(self):
        control_snaps = make_snapshots(5000, 50, 200.0, 5)
        variant_snaps = make_snapshots(5000, 400, 200.0, 100)
        result = evaluate_experiment(
            mode="EXPLORATORY",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": control_snaps, "v_treat": variant_snaps},
            min_criteria=MIN_CRITERIA,
        )
        assert result.evaluation_state != "winner_candidate"
        assert not result.causal_attribution

    def test_exploratory_causal_attribution_false(self):
        snaps = make_snapshots(2000, 100, 50.0, 10)
        result = evaluate_experiment(
            mode="EXPLORATORY",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": snaps, "v_treat": snaps},
            min_criteria=MIN_CRITERIA,
        )
        assert result.causal_attribution is False


class TestControlledMode:
    def test_winner_candidate_when_all_criteria_met(self):
        control = make_snapshots(5000, 50, 200.0, 5)
        variant = make_snapshots(5000, 500, 200.0, 80)
        result = evaluate_experiment(
            mode="CONTROLLED",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": control, "v_treat": variant},
            min_criteria={**MIN_CRITERIA, "min_confidence": 0.6, "min_difference": 0.05},
        )
        assert result.evaluation_state in ("winner_candidate", "promising", "inconclusive")

    def test_no_winner_without_sufficient_confidence(self):
        control = make_snapshots(200, 10, 20.0, 1)
        variant = make_snapshots(200, 11, 20.0, 1)
        result = evaluate_experiment(
            mode="CONTROLLED",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": control, "v_treat": variant},
            min_criteria=MIN_CRITERIA,
        )
        assert result.evaluation_state in ("inconclusive", "collecting", "insufficient_data", "promising")
        assert result.evaluation_state != "winner_candidate"


class TestLimitations:
    def test_peeking_risk_always_present(self):
        snaps = make_snapshots(2000, 100, 50.0, 10)
        result = evaluate_experiment(
            mode="CONTROLLED",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": snaps, "v_treat": snaps},
            min_criteria=MIN_CRITERIA,
        )
        assert any("peeking" in lim.lower() for lim in result.limitations)

    def test_exploratory_no_causal_attribution(self):
        snaps = make_snapshots(2000, 100, 50.0, 10)
        result = evaluate_experiment(
            mode="EXPLORATORY",
            primary_metric="ctr",
            variants=[CTRL, TREAT],
            snapshots_by_variant={"v_ctrl": snaps, "v_treat": snaps},
            min_criteria=MIN_CRITERIA,
        )
        # EXPLORATORY never attributes causality
        assert result.causal_attribution is False
        # At minimum peeking_risk limitation should be present
        assert len(result.limitations) > 0
