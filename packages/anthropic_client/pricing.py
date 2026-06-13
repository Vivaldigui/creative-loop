"""
Estimated cost calculation for Anthropic API calls.

Prices are approximate and may change. Always treat as estimate.
Cost is None when the model is unknown rather than guessing.
"""
from __future__ import annotations

# USD per million tokens (input, output) by model prefix
_PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-opus-4": (15.0, 75.0),
    "claude-opus-4-8": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "claude-haiku-4": (0.80, 4.0),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-5-haiku": (0.80, 4.0),
    "claude-3-opus": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    price_input_per_mtok: float | None = None,
    price_output_per_mtok: float | None = None,
) -> float | None:
    """Return estimated USD cost or None if unknown model and no override given."""
    if price_input_per_mtok is not None and price_output_per_mtok is not None:
        pin, pout = price_input_per_mtok, price_output_per_mtok
    else:
        pin, pout = _lookup(model)
        if pin is None:
            return None

    return (input_tokens * pin + output_tokens * pout) / 1_000_000


def _lookup(model: str) -> tuple[float | None, float | None]:
    model_l = model.lower()
    for prefix, (pin, pout) in _PRICE_TABLE.items():
        if model_l.startswith(prefix):
            return pin, pout
    return None, None
