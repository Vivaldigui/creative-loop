from __future__ import annotations

# (model, quality, size_str) → USD per image
_TABLE: dict[tuple[str, str, str], float] = {
    ("gpt-image-2", "standard", "1024x1024"): 0.040,
    ("gpt-image-2", "standard", "1024x1792"): 0.080,
    ("gpt-image-2", "standard", "1792x1024"): 0.080,
    ("gpt-image-2", "hd", "1024x1024"): 0.080,
    ("gpt-image-2", "hd", "1024x1792"): 0.120,
    ("gpt-image-2", "hd", "1792x1024"): 0.120,
    ("dall-e-3", "standard", "1024x1024"): 0.040,
    ("dall-e-3", "standard", "1024x1792"): 0.080,
    ("dall-e-3", "standard", "1792x1024"): 0.080,
    ("dall-e-3", "hd", "1024x1024"): 0.080,
    ("dall-e-3", "hd", "1024x1792"): 0.120,
    ("dall-e-3", "hd", "1792x1024"): 0.120,
}

_FALLBACK = 0.04  # conservative default when model is unknown


def estimate_cost(model: str, quality: str, width: int, height: int) -> float:
    """Return estimated USD cost per image for the given model/quality/size."""
    size = f"{width}x{height}"
    return _TABLE.get((model, quality, size), _FALLBACK)
