"""Unit tests for MetricNormalizer — priority ordering, nulls, unmapped, ROAS."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))

import json  # noqa: E402

from meta_client.normalize import NORMALIZATION_VERSION, MetricNormalizer  # noqa: E402

normalizer = MetricNormalizer()


def _load_fixture(name: str) -> list[dict]:
    path = ROOT / "packages" / "meta_client" / "fixtures" / name
    return json.loads(path.read_text())["data"]


# ── Priority ordering ─────────────────────────────────────────────

def test_omni_purchase_takes_priority_over_pixel_purchase():
    row = {
        "actions": [
            {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "5"},
            {"action_type": "omni_purchase", "value": "10"},
        ],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.purchases == 10  # omni_purchase wins (first in _ACTION_MAP)


def test_omni_add_to_cart_takes_priority_over_plain():
    row = {
        "actions": [
            {"action_type": "add_to_cart", "value": "3"},
            {"action_type": "omni_add_to_cart", "value": "7"},
        ],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.adds_to_cart == 7


def test_lead_priority_over_onsite_grouped():
    row = {
        "actions": [
            {"action_type": "onsite_conversion.lead_grouped", "value": "45"},
            {"action_type": "lead", "value": "45"},
        ],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.leads == 45


# ── Null handling ─────────────────────────────────────────────────

def test_null_row_produces_all_none():
    row = {
        "impressions": None,
        "reach": None,
        "spend": None,
        "clicks": None,
        "ctr": None,
        "cpc": None,
        "cpm": None,
        "actions": [],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.impressions is None
    assert m.spend is None
    assert m.purchases is None
    assert m.leads is None
    assert m.roas is None
    assert m.roas_source is None
    assert m.unmapped_actions == []


def test_empty_string_fields_become_none():
    row = {
        "impressions": "",
        "spend": "",
        "clicks": "",
        "actions": [],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.impressions is None
    assert m.spend is None


def test_inline_link_clicks_empty_string_is_none():
    """Empty string for inline_link_clicks (from dirty fixture) must not crash."""
    row = {
        "inline_link_clicks": "",
        "actions": [],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.link_clicks is None


# ── Unmapped actions ─────────────────────────────────────────────

def test_unmapped_actions_are_preserved():
    row = {
        "actions": [
            {"action_type": "omni_purchase", "value": "5"},
            {"action_type": "unknown_future_action", "value": "99"},
            {"action_type": "video_thruplay_watched", "value": "200"},
        ],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    unmapped_types = {u["action_type"] for u in m.unmapped_actions}
    assert "unknown_future_action" in unmapped_types
    assert "video_thruplay_watched" in unmapped_types
    assert "omni_purchase" not in unmapped_types  # was mapped


def test_zero_value_action_included():
    row = {
        "actions": [{"action_type": "video_view", "value": "0"}],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert any(u["action_type"] == "video_view" for u in m.unmapped_actions)


# ── ROAS ──────────────────────────────────────────────────────────

def test_roas_from_purchase_roas_field():
    row = {
        "spend": "420.00",
        "actions": [{"action_type": "omni_purchase", "value": "42"}],
        "action_values": [{"action_type": "omni_purchase", "value": "1344.00"}],
        "purchase_roas": [{"action_type": "omni_purchase", "value": "3.2"}],
    }
    m = normalizer.normalize(row)
    assert m.roas == 3.2
    assert m.roas_source == "reported"


def test_roas_derived_when_no_purchase_roas():
    row = {
        "spend": "100.00",
        "actions": [{"action_type": "omni_purchase", "value": "10"}],
        "action_values": [{"action_type": "omni_purchase", "value": "350.00"}],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.roas is not None
    assert abs(m.roas - 3.5) < 0.01
    assert m.roas_source == "derived"


def test_roas_none_when_no_purchase_value_or_spend():
    row = {
        "spend": None,
        "actions": [],
        "action_values": [],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.roas is None
    assert m.roas_source is None


def test_roas_none_when_spend_is_zero():
    row = {
        "spend": "0",
        "actions": [{"action_type": "omni_purchase", "value": "5"}],
        "action_values": [{"action_type": "omni_purchase", "value": "100.00"}],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.roas is None  # division by zero avoided


# ── Bad float string ─────────────────────────────────────────────

def test_bad_action_value_string_is_ignored():
    """bad_value in action_values must not crash; purchase_value falls back to None."""
    row = {
        "spend": "100.00",
        "actions": [{"action_type": "omni_purchase", "value": "10"}],
        "action_values": [{"action_type": "omni_purchase", "value": "bad_value"}],
        "purchase_roas": [],
    }
    m = normalizer.normalize(row)
    assert m.purchase_value is None
    assert m.roas is None


# ── Normalization version ────────────────────────────────────────

def test_normalization_version_set():
    m = normalizer.normalize({"actions": [], "action_values": [], "purchase_roas": []})
    assert m.normalization_version == NORMALIZATION_VERSION


# ── Clean fixture ────────────────────────────────────────────────

def test_clean_fixture_ad001():
    rows = _load_fixture("insights.json")
    row = next(r for r in rows if r["ad_id"] == "mock_ad_001")
    m = normalizer.normalize(row)
    assert m.impressions == 50000
    assert m.spend == 420.0
    assert m.roas == 3.2
    assert m.roas_source == "reported"
    assert m.purchases == 42
    assert m.landing_page_views == 1450
    assert m.adds_to_cart == 120
    assert m.initiate_checkout == 65


def test_clean_fixture_leads_ad():
    rows = _load_fixture("insights.json")
    row = next(r for r in rows if r["ad_id"] == "mock_ad_005")
    m = normalizer.normalize(row)
    assert m.leads == 45
    assert m.purchases is None
    assert m.roas is None


# ── Dirty fixture ────────────────────────────────────────────────

def test_dirty_fixture_priority_ordering():
    """omni_purchase should win over offsite_conversion.fb_pixel_purchase."""
    rows = _load_fixture("insights_dirty.json")
    row = next(r for r in rows if r["ad_id"] == "mock_ad_dirty_001")
    m = normalizer.normalize(row)
    assert m.purchases == 12  # omni_purchase (12) not pixel_purchase (10)


def test_dirty_fixture_null_row():
    rows = _load_fixture("insights_dirty.json")
    row = next(r for r in rows if r["ad_id"] == "mock_ad_dirty_002")
    m = normalizer.normalize(row)
    assert m.impressions is None
    assert m.spend is None
    assert m.unmapped_actions == []
