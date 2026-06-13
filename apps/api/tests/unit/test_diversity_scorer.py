"""Unit tests for experiment_engine.diversity_scorer."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from packages.experiment_engine.diversity_scorer import DiversityScorer, diversity_score


def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class TestNearIdenticalPrompt:
    def test_identical_hash_penalty(self):
        h = make_hash("same prompt")
        result = DiversityScorer().score(
            candidate_prompt_hash=h,
            existing_prompt_hashes=[h, h],
        )
        assert result.score < 0.9
        assert any("identical" in r.lower() or "near" in r.lower() for r in result.reasons)

    def test_different_hash_no_penalty(self):
        result = DiversityScorer().score(
            candidate_prompt_hash=make_hash("new prompt abc"),
            existing_prompt_hashes=[make_hash("other prompt xyz")],
        )
        assert result.score >= 0.9


class TestVariationChainDepth:
    def test_deep_chain_penalty(self):
        result = DiversityScorer().score(
            candidate_prompt_hash=None,
            variation_depth=5,
            max_variation_depth=3,
        )
        assert result.score < 1.0
        assert any("chain" in r.lower() or "depth" in r.lower() or "variation" in r.lower() for r in result.reasons)

    def test_acceptable_depth_no_penalty(self):
        result = DiversityScorer().score(
            candidate_prompt_hash=None,
            variation_depth=2,
            max_variation_depth=3,
        )
        chain_penalized = any("chain" in r.lower() or "depth" in r.lower() for r in result.reasons)
        assert not chain_penalized or result.score >= 0.8


class TestExcessiveLearningReuse:
    def test_excessive_reuse_penalty(self):
        result = DiversityScorer().score(
            candidate_prompt_hash=None,
            learning_reuse_count=5,
            max_learning_reuse=3,
        )
        assert result.score < 1.0
        assert any("learning" in r.lower() or "reuse" in r.lower() for r in result.reasons)

    def test_acceptable_reuse_no_penalty(self):
        result = DiversityScorer().score(
            candidate_prompt_hash=None,
            learning_reuse_count=2,
            max_learning_reuse=3,
        )
        reuse_penalized = any("reuse" in r.lower() for r in result.reasons)
        assert not reuse_penalized or result.score >= 0.8


class TestScoreRange:
    def test_score_between_zero_and_one(self):
        for depth in range(6):
            for reuse in range(6):
                result = DiversityScorer().score(candidate_prompt_hash=None, variation_depth=depth, learning_reuse_count=reuse)
                assert 0.0 <= result.score <= 1.0

    def test_empty_inputs_returns_one(self):
        result = DiversityScorer().score(candidate_prompt_hash=None)
        assert result.score == 1.0
        assert result.reasons == []


class TestConvenienceFunction:
    def test_diversity_score_returns_float(self):
        score = diversity_score(
            candidate_prompt_hash=make_hash("test"),
            existing_prompt_hashes=[make_hash("other")],
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
