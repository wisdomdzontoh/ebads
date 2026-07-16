"""Matching algorithms registry (docs/03-algorithms.md §4-6).

``ALGORITHMS`` maps each ``AlgorithmName`` to its singleton implementation, so the Selector
and the scoring pipeline look an algorithm up by name.
"""

from app.domain.allocation.algorithms.base import (
    MatchingAlgorithm,
    ScoreInputs,
    weighted_score,
)
from app.domain.allocation.algorithms.greedy import GreedyAlgorithm
from app.domain.allocation.algorithms.urgency_adaptive import UrgencyAdaptiveAlgorithm
from app.domain.allocation.algorithms.weighted import WeightedAlgorithm
from app.parameters import AlgorithmName

ALGORITHMS: dict[AlgorithmName, MatchingAlgorithm] = {
    AlgorithmName.GREEDY: GreedyAlgorithm(),
    AlgorithmName.WEIGHTED: WeightedAlgorithm(),
    AlgorithmName.URGENCY_ADAPTIVE: UrgencyAdaptiveAlgorithm(),
}

__all__ = [
    "ALGORITHMS",
    "GreedyAlgorithm",
    "MatchingAlgorithm",
    "ScoreInputs",
    "UrgencyAdaptiveAlgorithm",
    "WeightedAlgorithm",
    "weighted_score",
]
