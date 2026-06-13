"""
DiversityScorer — penalizes redundant creative/prompt suggestions.

Applied before generating a new round suggestion to avoid:
- Near-identical prompts (content_hash distance)
- Visually repeated creatives (pHash Hamming)
- Deep variation chains (variation_of_id depth)
- Excessive reuse of the same learning
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DiversityScore:
    """Score in [0, 1]; higher = more diverse from existing work."""
    score: float
    reasons: list[str]


class DiversityScorer:
    """
    Stateless scorer.  All inputs are plain dicts.

    Usage:
        scorer = DiversityScorer()
        result = scorer.score(
            candidate_prompt_hash="...",
            existing_prompt_hashes=[...],
            candidate_phash="...",
            existing_phashes=[...],
            variation_depth=0,
            learning_reuse_count=0,
        )
    """

    PHASH_BITS = 64  # 64-bit perceptual hash

    def score(
        self,
        candidate_prompt_hash: str | None,
        existing_prompt_hashes: list[str] | None = None,
        candidate_phash: str | None = None,
        existing_phashes: list[str] | None = None,
        variation_depth: int = 0,
        learning_reuse_count: int = 0,
        max_variation_depth: int = 3,
        max_learning_reuse: int = 3,
    ) -> DiversityScore:
        penalties: list[float] = []
        reasons: list[str] = []

        # Penalty 1: near-identical prompt
        if candidate_prompt_hash and existing_prompt_hashes:
            min_dist = min(
                _hex_bit_distance(candidate_prompt_hash, h)
                for h in existing_prompt_hashes
                if len(h) == len(candidate_prompt_hash)
            ) if any(len(h) == len(candidate_prompt_hash) for h in existing_prompt_hashes) else 1.0
            if min_dist < 0.05:
                penalties.append(0.8)
                reasons.append("prompt_nearly_identical")
            elif min_dist < 0.15:
                penalties.append(0.4)
                reasons.append("prompt_very_similar")

        # Penalty 2: visually repeated creative (pHash Hamming)
        if candidate_phash and existing_phashes:
            min_hamming = min(
                _hamming_distance(candidate_phash, p)
                for p in existing_phashes
                if len(p) == len(candidate_phash)
            ) if any(len(p) == len(candidate_phash) for p in existing_phashes) else self.PHASH_BITS
            hamming_ratio = min_hamming / self.PHASH_BITS
            if hamming_ratio < 0.1:
                penalties.append(0.7)
                reasons.append(f"creative_visually_repeated (hamming={min_hamming})")
            elif hamming_ratio < 0.25:
                penalties.append(0.35)
                reasons.append(f"creative_visually_similar (hamming={min_hamming})")

        # Penalty 3: deep variation chain
        if variation_depth >= max_variation_depth:
            factor = min(0.9, 0.3 * variation_depth)
            penalties.append(factor)
            reasons.append(f"variation_chain_too_deep (depth={variation_depth})")

        # Penalty 4: excessive learning reuse
        if learning_reuse_count >= max_learning_reuse:
            factor = min(0.8, 0.2 * learning_reuse_count)
            penalties.append(factor)
            reasons.append(f"learning_overused (reuse_count={learning_reuse_count})")

        # Combine penalties multiplicatively then invert
        combined_penalty = 1.0
        for p in penalties:
            combined_penalty *= (1.0 - p)
        final_score = combined_penalty

        return DiversityScore(score=max(0.0, min(1.0, final_score)), reasons=reasons)


def diversity_score(
    candidate_prompt_hash: str | None,
    existing_prompt_hashes: list[str] | None = None,
    **kwargs: Any,
) -> float:
    """Convenience function — returns scalar score."""
    return DiversityScorer().score(
        candidate_prompt_hash=candidate_prompt_hash,
        existing_prompt_hashes=existing_prompt_hashes,
        **kwargs,
    ).score


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hamming_distance(a: str, b: str) -> int:
    """Hamming distance between two hex strings of equal length."""
    if len(a) != len(b):
        return len(a) * 4  # treat as maximally different
    try:
        int_a = int(a, 16)
        int_b = int(b, 16)
        xor = int_a ^ int_b
        return bin(xor).count("1")
    except ValueError:
        return len(a) * 4


def _hex_bit_distance(a: str, b: str) -> float:
    """Normalised bit-difference [0,1] between two hex digest strings."""
    if len(a) != len(b) or len(a) == 0:
        return 1.0
    try:
        int_a = int(a, 16)
        int_b = int(b, 16)
        xor = int_a ^ int_b
        bits = len(a) * 4
        return bin(xor).count("1") / bits
    except ValueError:
        return 1.0
