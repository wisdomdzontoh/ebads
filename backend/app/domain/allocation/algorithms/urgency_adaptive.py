"""Algorithm 3 — Urgency-Adaptive Weighted Scoring (docs/03-algorithms.md §6).

The deployed default. Same weighted formula as Algorithm 2, but the weight vector is a
function of urgency (docs/09 §5 / Table 3.5). Encoding urgency in the *weights* — not as a
scalar multiplier — is essential: a scalar ``M(u)·Score2`` cannot change the argmin for an
individually-processed request and was explicitly rejected (docs/03 §6). The deterministic
``M(u)`` regression guard (docs/12 §2) proves this implementation actually changes selections.
"""

from __future__ import annotations

from app.domain.allocation.algorithms.base import (
    MatchingAlgorithm,
    ScoreInputs,
    weighted_score,
)
from app.parameters import ALGORITHM_3_WEIGHTS, AlgorithmName, Urgency, WeightVector


class UrgencyAdaptiveAlgorithm(MatchingAlgorithm):
    """Urgency-adaptive weighted scoring (docs/03 §6)."""

    name = AlgorithmName.URGENCY_ADAPTIVE

    def weight_vector(self, urgency: Urgency) -> WeightVector | None:
        """Return the weight vector for this urgency (docs/09 §5)."""
        return ALGORITHM_3_WEIGHTS[urgency]

    def score(self, inputs: ScoreInputs, weights: WeightVector | None) -> float:
        """Score with the urgency-specific weights via the shared weighted formula."""
        assert weights is not None  # weight_vector never returns None for this algorithm
        return weighted_score(inputs, weights)
