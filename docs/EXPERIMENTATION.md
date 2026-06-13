# Experimentation & Learning (Phase 7)

This document describes the experiment lifecycle, the conservative evaluation engine, the learning lifecycle, diversity-scored next-round suggestions, the worker/Beat schedule, and the reports — plus the safety guarantees that govern all of them.

The guiding principle: **the platform measures and suggests; humans decide.** Nothing in this phase trains a model, generates a creative, changes a budget, or declares a winner on its own.

---

## Mandatory safety rules

These are enforced in code, not just convention:

| Rule | Where it is enforced |
|---|---|
| No automatic fine-tuning | No training/tuning code path exists; suggestions are human-reviewed only |
| No automatic image generation | `NextRoundService` records `auto_image_generation: False`; suggestions start `pending_approval` |
| No automatic budget changes | `DecisionService` never writes budget; `suggested_action` is advisory, `executed_action` is human-only |
| Never declare a winner without sufficient data | `evaluate_experiment()` gates `winner_candidate` behind all minimum criteria + maturation |
| New learnings start `provisional` | `LearningService.create()` always sets `status="provisional"` |
| Learning confirmation requires human review | `confirm()` requires a reviewer; `reject()` requires a mandatory comment |
| EXPLORATORY never attributes causality | `causal_attribution=False` always; state capped at `promising` |
| CONTROLLED enforces single-variable isolation | `guard_controlled_single_variable` blocks start otherwise |
| Workers are idempotent | `uq_variant_snapshot_key` unique constraint; upsert, never duplicate |
| Timezone `America/Sao_Paulo` | All Beat schedules and report windows |
| AuditLog for every sensitive action | create/start/stop/complete/decision/learning/suggestion |

All earlier protections (DRY_RUN, REQUIRE_HUMAN_APPROVAL, idempotency, budget limits, org isolation) remain in force.

---

## Experiment modes

| | **EXPLORATORY** | **CONTROLLED** |
|---|---|---|
| Variables per variant | Many allowed | Exactly one (== `primary_variable`) |
| `causal_attribution` | **Always False** | True only when `winner_candidate` |
| Max reachable state | `promising` | `winner_candidate` |
| Purpose | Broad idea discovery | Causal A/B testing |
| Start guard | Single-variable check skipped | `guard_controlled_single_variable` blocks multi-variable variants |

EXPLORATORY is for "what's worth testing"; CONTROLLED is for "does this one change cause a lift". The engine refuses to claim causality outside CONTROLLED single-variable experiments.

---

## Experiment lifecycle

```
draft ──start──▶ running ──┬──stop────▶ stopped
                           └──complete─▶ completed
```

- **draft** — created with or without variants. A draft with no variants is allowed (`guard_has_baseline` only warns); a draft with variants must have exactly one `is_control` variant before it can start.
- **start** — re-runs all guards. Blocks if any guard fails (missing baseline, multi-variable in CONTROLLED, budget over cap). Sets `started_at`.
- **stop** — manual or safety-triggered halt; records `stop_reason`.
- **complete** — formal conclusion; records `stop_reason` (e.g. `winner_candidate`).

Lifecycle service methods re-query with `selectinload(Experiment.variants)` after commit (not `db.refresh`), so the `variants` relationship is eagerly loaded before serialization — this avoids `MissingGreenlet` errors from lazy-loading outside an async greenlet.

### Guards (`packages/experiment_engine/guards.py`)

Run on create and again on start. Severity is `pass`, `warning`, or `blocked`; only `blocked` prevents the action.

| Guard | Severity when failing | Notes |
|---|---|---|
| `guard_has_baseline` | blocked (warning if no variants yet) | Exactly one `is_control` variant |
| `guard_controlled_single_variable` | blocked | CONTROLLED only; one variable == `primary_variable` |
| `guard_each_variant_has_hypothesis` | warning | Traceability, not a hard stop |
| `guard_controlled_comparable_budget` | warning | Budgets within tolerance for fair comparison |
| `guard_controlled_comparable_audience` | warning | Same audience definition across variants |
| `guard_controlled_comparable_window` | warning | Experiment window defined |
| `guard_experiment_budget` | blocked | `planned_budget` ≤ `MAX_EXPERIMENT_BUDGET` |

---

## The evaluator (`packages/experiment_engine/evaluator.py`)

`evaluate_experiment()` is a **pure function** — no DB access. It takes the mode, primary metric, variant descriptors, and per-variant snapshots, and returns an `EvaluationResult`.

### States

```
insufficient_data   minimum criteria not met at all (>2 sufficiency issues)
collecting          some criteria met, not all (1–2 issues)
inconclusive        sufficient data, no clear direction
promising           positive direction, below winner threshold
underperforming     consistently negative direction
winner_candidate    ALL criteria + diff ≥ min_difference + confidence ≥ min_confidence  (CONTROLLED only)
completed           manually completed
stopped_for_safety  halted on a safety signal
```

### Minimum criteria (defaults)

`min_criteria` is a JSON blob on the experiment. Defaults when unset:

| Key | Default | Meaning |
|---|---|---|
| `min_spend` | 50.0 | Minimum spend per variant |
| `min_impressions` | 1000 | Minimum impressions per variant |
| `min_clicks` | 50 | Minimum clicks per variant |
| `min_conversions` | 0 | Minimum conversions per variant |
| `min_days` | 3 | Minimum active days |
| `min_difference` | 0.10 | Minimum relative lift to call a winner |
| `min_confidence` | 0.80 | Minimum posterior confidence to call a winner |
| `max_frequency` | 4.0 | Fatigue threshold (warns above) |
| `maturation_window_days` | 3 | Days a snapshot must age before it counts |

Only **matured** snapshots are aggregated (`matured_only=True`). A variant with zero matured snapshots is a sufficiency issue.

### Statistical confidence (`packages/analytics_engine/stats.py`)

Confidence is a **Beta-Binomial posterior** — `P(test rate > control rate)` for rate metrics (CTR uses clicks/impressions; CVR uses conversions/clicks). It is computed with pure Python (`math.lgamma` + a Lentz continued-fraction for the regularized incomplete beta) — **no scipy dependency**. Continuous metrics (ROAS, CPA) assume no distribution and return `None` confidence rather than fabricate one. Rate metrics need ≥ 10 trials per arm before any confidence is reported.

### Peeking risk

Every evaluation appends a `peeking_risk` limitation: repeated mid-flight checking inflates the false-positive rate. The platform never hides this caveat. The full evaluation history is preserved (append-only) so peeking is auditable.

### Why a winner is hard to reach

`winner_candidate` requires **all** of: every variant meets `min_spend`/`min_impressions`/`min_clicks` and has matured data, the best lift ≥ `min_difference`, the posterior confidence ≥ `min_confidence`, **and** the mode is CONTROLLED. Anything short of that lands in `promising`, `inconclusive`, `underperforming`, `collecting`, or `insufficient_data`.

---

## Aggregation (`packages/analytics_engine/aggregator.py`)

Per-variant metrics are aggregated with **winsorization** — extreme daily values are clamped to configured percentiles so a single runaway ROAS day cannot dominate the verdict. `safe_sum` returns `None` (not `0.0`) when every input is null, preserving the distinction between "no data" and "measured zero".

---

## Decisions (`OptimizationDecision`)

A decision links an evaluation to a human-readable recommendation. It is **advisory only**:

- `suggested_action` ∈ `{continue, pause, review, create_new_hypothesis, wait_more_data}`
- `executed_action` is filled **only** when a human explicitly acts
- Budget is **never** changed — `max_automatic_budget_increase_percent=0`

The service rejects any unknown `suggested_action`.

---

## Learning lifecycle (`Learning`)

```
(created) ─▶ provisional ──human review──▶ confirmed
                          └─comment req.──▶ rejected
```

- Every learning is born `provisional` — never `confirmed`.
- `confirm()` requires a human reviewer (`reviewed_by_id`, `reviewed_at`).
- `reject()` requires a mandatory `review_comment` with counter-evidence.
- `limitations` are stored with every learning — no learning is treated as definitive truth.
- `supersedes_id` records when a newer learning overrides an older one.
- Each learning carries a 128-d embedding stored as JSONB `list[float]` (pgvector in production). In dev/tests a deterministic SHA256-based mock embedding is used — no external embedding API is called.

---

## Diversity scoring & next round

`NextRoundService` proposes the next experiment round. Before proposing, `DiversityScorer` (`packages/experiment_engine/diversity_scorer.py`) penalizes four redundancy types and returns a score in `[0, 1]` (higher = more novel):

1. **Near-identical prompts** — normalized bit-distance between content hashes
2. **Visual repetition** — pHash Hamming distance between creatives
3. **Deep variation chains** — `variation_of_id` depth beyond `max_variation_depth`
4. **Excessive learning reuse** — same learning reused beyond `max_learning_reuse`

Penalties combine multiplicatively. The resulting `ExperimentSuggestion`:

- records **`auto_image_generation: False`** — no creative is generated automatically
- starts **`pending_approval`** — never auto-approved, never auto-published
- requires explicit human approval before any downstream generation or publication

`LearningUsage` rows track which confirmed learnings fed each suggestion.

---

## Workers & Beat schedule

All Phase 7 Celery tasks are **idempotent**, set `max_retries=0` and `acks_late=True`, and bridge sync Celery → async via a fresh event loop.

| Task | Purpose |
|---|---|
| `collect_variant_metrics` / `dispatch_metric_collection` | Upsert per-variant snapshots (idempotent) |
| `compute_evaluations` | Append-only evaluation per running experiment |
| `detect_anomalous_spend` | Flag (not pause) abnormal spend |
| `detect_zero_conversions` | Flag spend with no conversions |
| `detect_rejected_ads` | Flag Meta-rejected variants |
| `update_experiment_status` / `flag_experiments_ready` | Surface experiments needing human attention |
| `daily_report` / `weekly_report` | Build reports |
| `suggest_next_round` | Generate diversity-scored suggestions |

### Idempotency

`collect_variant_metrics` upserts `VariantPerformanceSnapshot` keyed by `uq_variant_snapshot_key` = (`variant_id`, `date_start`, `date_stop`, `level`, `breakdown_key`, `attribution_window`). Re-running the same window updates the existing row rather than inserting a duplicate.

### Anomaly detectors never act on budget

The detectors raise human-facing flags only. They never pause an ad or change a budget — those remain manual actions.

### Timezone

The Beat schedule sets `timezone=America/Sao_Paulo`; daily/weekly report crontabs and report windows are all computed in São Paulo local time.

---

## Reports

| Endpoint | Description |
|---|---|
| `GET /reports/daily` | Daily aggregate: active experiments, evaluations, alerts |
| `GET /reports/weekly` | Weekly rollup with the same structure over a 7-day window |

Both are read-only aggregations over existing data; they trigger no side effects.

---

## Data model

```
Experiment  [mode, primary_variable, min_criteria(JSON), window, planned_budget,
             evaluation_state, baseline_variant_id → ExperimentVariant]
  ├── ExperimentVariant  [is_control, variant_role, changed_variables, allocated_budget,
  │                       creative_id, prompt_version_id, published_ad_id]
  │     └── VariantPerformanceSnapshot  [metrics…, is_matured, attribution_window,
  │                                      uq_variant_snapshot_key]
  ├── ExperimentEvaluation (append-only)  [evaluation_state, per_variant_result,
  │                                        confidence, limitations, causal_attribution]
  │     └── OptimizationDecision  [suggested_action, executed_action(human-only)]
  └── ExperimentSuggestion  [selected_learning_ids, diversity_score, status=pending_approval]

Learning  [observed_pattern, evidence, confidence, status(provisional→confirmed/rejected),
           embedding(JSONB), supersedes_id]
  └── LearningUsage  [learning_id, suggestion_id|prompt_version_id, used_at]
```

The circular FK `Experiment.baseline_variant_id → ExperimentVariant.id` uses `use_alter=True` so the migration can create both tables. The migration `a1b2c3d4e5f6` uses `batch_alter_table` for SQLite compatibility.

---

## API reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST / GET | `/experiments` | editor+ / auth | Create / list (mode + status filters) |
| GET | `/experiments/{id}` | auth | Detail + variants |
| POST | `/experiments/{id}/start` | editor+ | Run guards, draft→running |
| POST | `/experiments/{id}/stop` | editor+ | Stop with reason |
| POST | `/experiments/{id}/complete` | owner | Complete with stop reason |
| POST | `/experiments/{id}/evaluate` | editor+ | Append-only evaluation |
| GET | `/experiments/{id}/metrics` | auth | Variant snapshots |
| POST / GET | `/experiments/{id}/decisions` | editor+ / auth | Create / list advisory decisions |
| POST | `/experiments/{id}/suggest-next-round` | editor+ | Generate diversity-scored suggestion |
| GET | `/suggestions` | auth | List suggestions |
| POST | `/suggestions/{id}/approve` · `/reject` | admin+ | Human approval gate |
| POST / GET | `/learnings` | editor+ / auth | Create (provisional) / list |
| GET | `/learnings/{id}` | auth | Learning detail |
| POST | `/learnings/{id}/confirm` | admin+ | Human review → confirmed |
| POST | `/learnings/{id}/reject` | admin+ | Reject with mandatory comment |

(Roles: `owner` > `admin` > `editor` > `viewer`. "editor+" = owner/admin/editor; "admin+" = owner/admin; "auth" = any authenticated user.)
| GET | `/reports/daily` · `/reports/weekly` | auth | Aggregated reports (SP timezone) |

---

## Frontend pages

| Route | Purpose |
|---|---|
| `/experiments` | List with mode/status filters |
| `/experiments/new` | Create form with EXPLORATORY/CONTROLLED selector |
| `/experiments/[id]` | Detail: lifecycle actions, evaluation, metrics, decisions, suggestions |
| `/learnings` | Learning list with confirm/reject actions |
| `/suggestions` | Suggestion list with approve/reject actions |
| `/reports` | Daily / weekly report tabs |

---

## Testing

79 Phase 7 tests (on top of 343 from Phase 6 → **422 total**):

| Suite | Count | Covers |
|---|---|---|
| `test_stats.py` | 22 | Beta-Binomial, confidence, edge cases |
| `test_experiment_guards.py` | 12 | Baseline, single-variable, hypothesis, run-all |
| `test_evaluator.py` | 9 | Insufficient data, EXPLORATORY caps, CONTROLLED winner, peeking |
| `test_diversity_scorer.py` | 9 | Four penalty types, embeddings |
| `test_aggregator.py` | 9 | Winsorization, safe_sum, per-variant |
| `test_experiment_flow.py` | 18 | CRUD, org isolation, lifecycle, append-only evaluation, decision-does-not-change-budget, learning lifecycle |

All tests run against in-memory SQLite — no external services.

```bash
pytest apps/api/tests/ -q
```

---

## Seed data

`scripts/seed.py` creates a fictitious running CONTROLLED experiment ("Background Color Test") with two variants (white vs pink background), two matured snapshots, one `promising` evaluation, one advisory decision (`continue`, no budget change), two learnings (one `confirmed`, one `provisional`), and one `pending_approval` suggestion — enough to exercise every Phase 7 screen. All records are marked `is_fictitious=True`.
