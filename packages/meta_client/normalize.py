from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

NORMALIZATION_VERSION = "2"

# Priority-ordered mapping: first match for each target field wins.
# Entries are checked in order; the first action_type present in the
# raw actions list is used for that target field.
_ACTION_MAP: list[tuple[str, str]] = [
    # purchases
    ("omni_purchase", "purchases"),
    ("purchase", "purchases"),
    ("offsite_conversion.fb_pixel_purchase", "purchases"),
    # adds_to_cart
    ("omni_add_to_cart", "adds_to_cart"),
    ("add_to_cart", "adds_to_cart"),
    ("offsite_conversion.fb_pixel_add_to_cart", "adds_to_cart"),
    # initiate_checkout
    ("omni_initiated_checkout", "initiate_checkout"),
    ("initiate_checkout", "initiate_checkout"),
    ("offsite_conversion.fb_pixel_initiate_checkout", "initiate_checkout"),
    # leads
    ("lead", "leads"),
    ("onsite_conversion.lead_grouped", "leads"),
    ("offsite_conversion.fb_pixel_lead", "leads"),
    # landing_page_views
    ("landing_page_view", "landing_page_views"),
    # link_clicks
    ("link_click", "link_clicks"),
    ("inline_link_clicks", "link_clicks"),
]

# Fields produced by normalize(); null means "not available"
_FLAT_FIELDS = {
    "purchases", "adds_to_cart", "initiate_checkout", "leads",
    "landing_page_views", "link_clicks",
}


@dataclass
class NormalizedMetrics:
    impressions: int | None = None
    reach: int | None = None
    frequency: float | None = None
    spend: float | None = None
    clicks: int | None = None
    link_clicks: int | None = None
    ctr: float | None = None
    cpc: float | None = None
    cpm: float | None = None
    landing_page_views: int | None = None
    adds_to_cart: int | None = None
    initiate_checkout: int | None = None
    purchases: int | None = None
    leads: int | None = None
    cost_per_result: float | None = None
    purchase_value: float | None = None
    roas: float | None = None
    roas_source: str | None = None        # "reported" | "derived" | None
    currency: str | None = None
    attribution_window: str | None = None
    unmapped_actions: list[dict[str, Any]] = field(default_factory=list)
    normalization_version: str = NORMALIZATION_VERSION


class MetricNormalizer:
    """
    Maps a raw Graph API insights row to NormalizedMetrics.
    All fields are nullable: absence == null, never 0 by default.
    Preserves unmapped action_types for audit.
    """

    def normalize(self, row: dict[str, Any]) -> NormalizedMetrics:
        m = NormalizedMetrics()

        # ── Direct numeric fields ────────────────────────────────
        m.impressions = _int(row.get("impressions"))
        m.reach = _int(row.get("reach"))
        m.frequency = _float(row.get("frequency"))
        m.spend = _float(row.get("spend"))
        m.clicks = _int(row.get("clicks"))
        m.ctr = _float(row.get("ctr"))
        m.cpc = _float(row.get("cpc"))
        m.cpm = _float(row.get("cpm"))
        m.currency = row.get("account_currency") or row.get("currency")
        m.attribution_window = row.get("attribution_setting")

        # ── Actions list → flat fields ───────────────────────────
        actions: list[dict[str, Any]] = row.get("actions") or []
        action_values: list[dict[str, Any]] = row.get("action_values") or []

        action_lookup = _action_lookup(actions)
        value_lookup = _action_lookup(action_values)

        mapped_types: set[str] = set()
        resolved: dict[str, int] = {}

        for action_type, target_field in _ACTION_MAP:
            if target_field in resolved:
                continue  # already filled by a higher-priority entry
            val = action_lookup.get(action_type)
            if val is not None:
                resolved[target_field] = val
                mapped_types.add(action_type)

        m.link_clicks = resolved.get("link_clicks") or _int(row.get("inline_link_clicks"))
        m.landing_page_views = resolved.get("landing_page_views")
        m.adds_to_cart = resolved.get("adds_to_cart")
        m.initiate_checkout = resolved.get("initiate_checkout")
        m.purchases = resolved.get("purchases")
        m.leads = resolved.get("leads")

        # ── Purchase value ───────────────────────────────────────
        pv = None
        for at in ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase"):
            v = value_lookup.get(at)
            if v is not None:
                pv = float(v)
                break
        m.purchase_value = pv

        # ── ROAS ────────────────────────────────────────────────
        roas_list: list[dict[str, Any]] = row.get("purchase_roas") or []
        if roas_list:
            first = roas_list[0]
            m.roas = _float(first.get("value"))
            m.roas_source = "reported"
        elif m.purchase_value is not None and m.spend and m.spend > 0:
            m.roas = round(m.purchase_value / m.spend, 4)
            m.roas_source = "derived"

        # ── Cost per result (ambiguous — null unless clear) ───────
        # We intentionally leave cost_per_result null in Phase 2;
        # it depends on the objective's optimization goal.
        m.cost_per_result = None

        # ── Unmapped actions ────────────────────────────────────
        unmapped = []
        for entry in actions:
            at = entry.get("action_type", "")
            if at and at not in mapped_types:
                unmapped.append({"action_type": at, "value": entry.get("value")})
        m.unmapped_actions = unmapped

        return m


# ── Helpers ───────────────────────────────────────────────────────

def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def _float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return None


def _action_lookup(entries: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in entries:
        at = e.get("action_type")
        val = e.get("value")
        if at and val is not None:
            try:
                out[at] = float(str(val))
            except (ValueError, TypeError):
                pass
    return out
