"""Matching-algorithm interface and shared scoring (docs/03-algorithms.md §4-6, §9).

All three algorithms share the same shape: pick the candidate with the lowest score, with a
deterministic tie-break. They differ only in how a candidate's score is computed and which
weight vector (if any) applies. ``weighted_score`` is the common formula used by Algorithms
2 and 3; Greedy overrides scoring entirely (it ranks by raw travel time).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.parameters import AlgorithmName, Urgency, WeightVector


@dataclass(frozen=True)
class ScoreInputs:
    """The per-candidate quantities every algorithm may use to score (docs/03 §5-6)."""

    t_hat: float
    b_hat: float
    c_hat: float
    travel_time_min: float


def weighted_score(inputs: ScoreInputs, weights: WeightVector) -> float:
    """Lower-is-better weighted score shared by Algorithms 2 and 3 (docs/03 §5-6).

    ``w_t·t̂ + w_b·(1−b̂) + w_c·(1−ĉ)`` — every term is a "cost" (travel time, bed scarcity,
    capability mismatch), so the best facility is the argmin.
    """
    return (
        weights.w_t * inputs.t_hat
        + weights.w_b * (1.0 - inputs.b_hat)
        + weights.w_c * (1.0 - inputs.c_hat)
    )


class MatchingAlgorithm(ABC):
    """One matching algorithm (docs/03-algorithms.md §4-6)."""

    name: AlgorithmName

    @abstractmethod
    def weight_vector(self, urgency: Urgency) -> WeightVector | None:
        """Return the weight vector applied for this urgency, or None (Greedy uses none)."""

    @abstractmethod
    def score(self, inputs: ScoreInputs, weights: WeightVector | None) -> float:
        """Return this candidate's score (lower is better)."""
