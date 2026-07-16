"""Algorithm 1 — Greedy Nearest-Facility (docs/03-algorithms.md §4).

Baseline, simulation-only (never deployed). Picks the reachable facility with the shortest
travel time: ``h* = argmin t(p, h)``. It ignores bed scarcity and capability, and carries no
weight vector (``weight_vector = null`` in the audit, docs/03 §4).
"""

from __future__ import annotations

from app.domain.allocation.algorithms.base import MatchingAlgorithm, ScoreInputs
from app.parameters import AlgorithmName, Urgency, WeightVector


class GreedyAlgorithm(MatchingAlgorithm):
    """Greedy nearest-facility baseline (docs/03 §4)."""

    name = AlgorithmName.GREEDY

    def weight_vector(self, urgency: Urgency) -> WeightVector | None:
        """Greedy applies no weights."""
        return None

    def score(self, inputs: ScoreInputs, weights: WeightVector | None) -> float:
        """Rank by raw travel time so the argmin is the nearest facility."""
        return inputs.travel_time_min
