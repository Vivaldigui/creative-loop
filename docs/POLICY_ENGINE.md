# Policy Engine

## Overview

The Policy Engine (`packages/policy_engine/engine.py`) is a rule-based compliance checker that scans creative text (prompt + copy) for patterns that could violate Meta Ads policies or applicable regulations.

## Important Notice

**The Policy Engine's PASS result does NOT mean the creative is approved by Meta Ads or any advertising platform.**

This is an internal compliance pre-check. Final approval is determined by Meta's own automated and human review systems, which are outside our control and are not emulated by this engine.

Every API response that includes a policy check result includes the following notice:

> "This creative passed the internal policy check. This does NOT guarantee approval by Meta Ads or any other platform."

This notice is immutable and cannot be suppressed.

## Result Classification

| Result  | Meaning                                                                          |
|---------|----------------------------------------------------------------------------------|
| PASS    | No policy flags found in the text. Internal check only — not a Meta approval.   |
| WARNING | Reviewer should validate before approving. Override with conscious comment.      |
| BLOCKED | Creative cannot be approved via the common flow. Owner can override with comment. |

## Rules

Rules are defined in `packages/policy_engine/engine.py` as `_BASE_RULES`. They are evaluated using Python `re.Pattern` against the full prompt text.

### BLOCKED Rules (applied to all segments unless noted)

| Rule ID                    | Pattern example                            | Notes                       |
|----------------------------|--------------------------------------------|-----------------------------|
| `guarantee_of_result`      | "garantia", "garantido"                    | Result guarantees           |
| `medical_treatment_claim`  | "cura", "tratamento"                       | Medical treatment claims    |
| `before_after_comparison`  | "antes e depois"                           | Prohibited comparison format|
| `weight_loss_guarantee`    | "Perca Xkg", "Emagreça Xkg"               | Weight loss with quantity   |
| `absolute_claim`           | "100% eficaz", "100% natural"             | Absolute efficacy claims    |
| `cure_claim`               | "cura definitiva", "cura total"            | Cure claims                 |
| `personal_attribute_targeting` | Attributes like race/religion/sexuality | Targeting protected groups |
| `discriminatory_language`  | "discriminação", "preconceito", "racismo"  | Hate speech / discrimination|
| `income_guarantee`         | "Faça mais dinheiro garantido"             | Income guarantees           |
| `rapid_weight_loss`        | "emagrecimento rápido"                     | Health/fitness segments     |
| `medical_approval_claim`   | "aprovado pela ANVISA/FDA"                 | Regulatory approval claims  |

### WARNING Rules (applied to all segments unless noted)

| Rule ID                     | Pattern example                        | Notes                    |
|-----------------------------|----------------------------------------|--------------------------|
| `false_urgency`             | "urgente", "não perca", "últimas vagas"| Scarcity manipulation    |
| `superlative_claim`         | "melhor do mundo", "melhor do Brasil"  | Unverifiable superlatives|
| `medical_reference`         | "médico", "Dr.", "Drª."               | Professional references  |
| `free_claim`                | "grátis", "free", "de graça"          | Free offers              |
| `exclusivity_claim`         | "premium", "exclusivo", "VIP"          | Exclusivity              |
| `unverified_claim`          | "comprovado", "clinicamente"           | Unverified effectiveness |
| `price_sensationalism`      | "preço imperdível"                     | Sensational pricing      |
| `price_mention`             | "R$ 99", "$ 29.99"                    | Price disclosure req.    |
| `third_party_trademark`     | "™", "®", "©"                         | Trademark usage          |
| `natural_without_side_effects` | "natural sem efeitos colaterais"   | Health/beauty/fitness    |

## Segment-Aware Rules

Some rules apply only to specific audience segments. Pass `segment="health"` or `segment="fitness"` to the `check()` method to activate them.

Supported segments: `health`, `fitness`, `beauty`.

## BLOCKED Override

A BLOCKED creative can only be approved by a user with the `owner` role when:
1. `ALLOW_BLOCKED_OVERRIDE=true` (disabled by default in production)
2. The owner explicitly sets `override_blocked=true` in the approval request
3. A non-empty comment justifying the override is provided

All overrides are recorded in the `approvals` table with `overridden_check_ids` containing the IDs of overridden checks. This is immutable and auditable.

## WARNING Confirmation

For WARNING-level findings, the reviewer must consciously approve the creative. The frontend approval interface shows the specific warnings and requires the reviewer to proceed with full awareness.

## Rule Set Versioning

Every `PolicyResult` includes a `rule_set_version` field (currently `"2.0.0"`). Policy check records in the database store this version, allowing you to re-evaluate past creatives against updated rules.

## Extending Rules

Add entries to `_BASE_RULES` in `packages/policy_engine/engine.py`:

```python
(
    re.compile(r"\bpattern_here\b", re.I),
    "blocked",           # or "warning"
    "rule_id_name",
    None,                # or {"health", "fitness"} for segment-specific
),
```

Bump `rule_set_version` in `PolicyEngine.__init__` when adding rules. The existing policy check records retain their original version and are unaffected.

## Testing

```bash
cd apps/api
pytest tests/unit/test_policy_engine.py tests/unit/test_policy_engine_p4.py -v
```
