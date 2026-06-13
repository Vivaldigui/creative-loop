# Metrics Normalization

## Why Normalization

The Meta Marketing API returns conversion actions as a nested `actions` list, with the same
conversion event reported under multiple `action_type` keys depending on the signal source
(pixel, omni, app). The same purchase might appear as:
- `omni_purchase`
- `purchase`
- `offsite_conversion.fb_pixel_purchase`

Without normalization, naively summing all three would triple-count the same event.

The `MetricNormalizer` class in `packages/meta_client/normalize.py` solves this via a
priority-ordered mapping.

---

## Priority Ordering

For each target field, only the **first matching** action_type in `_ACTION_MAP` is used.
Order matters: broader/newer signal types take priority.

```
omni_purchase > purchase > offsite_conversion.fb_pixel_purchase  → purchases
omni_add_to_cart > add_to_cart > offsite_conversion.*            → adds_to_cart
lead > onsite_conversion.lead_grouped > offsite_conversion.*     → leads
```

If the highest-priority entry exists, lower-priority entries for the same field are ignored.

---

## Null Semantics

**Null means absent, never zero.** A `None` value means the metric was not reported in this
period — it does not mean zero. This distinction matters for averaging: `None` values are
excluded from averages; `0` would drag them down.

Examples:
- Ad with no purchases → `purchases = None` (not `0`)
- Empty `actions` list → all action-derived fields are `None`
- `spend = "0"` → `spend = 0.0` (explicitly zero budget)

---

## ROAS

ROAS is tracked with its source method:

| `roas_source` | Description |
|---|---|
| `"reported"` | From `purchase_roas[0].value` in the API response (Meta's calculation) |
| `"derived"` | `purchase_value / spend` computed locally (used when `purchase_roas` is absent) |
| `None` | Not available (no purchase_value or spend is zero) |

**Prefer `roas_source="reported"`** when displaying to users — it uses Meta's attribution logic.
Derived ROAS is an approximation.

---

## Unmapped Actions

Any `action_type` not in `_ACTION_MAP` is preserved in `unmapped_actions` for audit:

```json
{
  "unmapped_actions": [
    {"action_type": "video_thruplay_watched", "value": 200},
    {"action_type": "unknown_future_action", "value": 5}
  ]
}
```

This allows adding new mappings later without losing historical data. The `normalization_version`
field tracks which version of `_ACTION_MAP` was used when a snapshot was created.

---

## Normalization Version

`NORMALIZATION_VERSION = "2"` is stored on every `PerformanceSnapshot` row.

When the mapping changes in a future phase, increment this value and re-normalize affected rows.
The version enables targeted re-runs without re-importing raw data from Meta.

---

## Field Reference

| Normalized Field | Source |
|---|---|
| `impressions` | `impressions` (string → int) |
| `reach` | `reach` |
| `frequency` | `frequency` |
| `spend` | `spend` (string → float) |
| `clicks` | `clicks` |
| `ctr` | `ctr` |
| `cpc` | `cpc` |
| `cpm` | `cpm` |
| `link_clicks` | `link_click` or `inline_link_clicks` action, fallback to `inline_link_clicks` field |
| `landing_page_views` | `landing_page_view` action |
| `adds_to_cart` | `omni_add_to_cart` > `add_to_cart` > pixel variant |
| `initiate_checkout` | `omni_initiated_checkout` > `initiate_checkout` > pixel variant |
| `purchases` | `omni_purchase` > `purchase` > pixel variant |
| `leads` | `lead` > `onsite_conversion.lead_grouped` > pixel variant |
| `purchase_value` | `action_values` for purchase action types (first match) |
| `roas` | `purchase_roas[0].value` or derived |
| `roas_source` | `"reported"` / `"derived"` / `None` |
| `currency` | `account_currency` or `currency` |
| `attribution_window` | `attribution_setting` |
| `unmapped_actions` | All action_types not in `_ACTION_MAP` |
| `normalization_version` | Constant `"2"` |

---

## Testing

Run normalization tests:

```bash
pytest apps/api/tests/unit/test_meta_normalize.py -v
```

The dirty fixture (`packages/meta_client/fixtures/insights_dirty.json`) covers:
- Priority ordering (omni > pixel)
- Bad float strings in action_values
- Unknown action_types → unmapped
- All-null row
