"""Algorithm 2 — Weighted Multi-Criteria Scoring (docs/03-algorithms.md §5).

Fixed weights ``(w_t, w_b, w_c) = (0.40, 0.35, 0.25)`` applied identically for every urgency.
Used as the safe fallback when urgency is missing/invalid, and as a simulation configuration.
"""

from __future__ import annotations

from app.domain.allocation.algorithms.base import (
    MatchingAlgorithm,
    ScoreInputs,
    weighted_score,
)
from app.parameters import ALGORITHM_2_WEIGHTS, AlgorithmName, Urgency, WeightVector


class WeightedAlgorithm(MatchingAlgorithm):
    """Fixed-weight multi-criteria scoring (docs/03 §5)."""

    name = AlgorithmName.WEIGHTED

    def weight_vector(self, urgency: Urgency) -> WeightVector | None:
        """Return the fixed Algorithm 2 weights, regardless of urgency."""
        return ALGORITHM_2_WEIGHTS

    def score(self, inputs: ScoreInputs, weights: WeightVector | None) -> float:
        """Score with the fixed weights via the shared weighted formula."""
        assert weights is not None  # weight_vector never returns None for this algorithm
        return weighted_score(inputs, weights)
