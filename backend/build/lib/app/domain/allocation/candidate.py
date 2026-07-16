"""Value objects for the scoring pipeline (docs/03-algorithms.md).

``Candidate`` is the id-agnostic unit the pure scoring functions operate on: it carries only
what the hard filter and the algorithms need (travel time, available beds, tier). Using a
plain string ``facility_id`` keeps the deterministic test vectors (which use ids like "A")
and the live engine (which uses UUID strings) on exactly the same code path.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.parameters import Tier


@dataclass(frozen=True)
class Candidate:
    """A facility under consideration, before scoring (docs/03 §0)."""

    facility_id: str
    tier: Tier
    travel_time_min: float
    available_beds: int
    is_estimated_travel_time: bool = False


@dataclass(frozen=True)
class ScoredCandidate:
    """A candidate plus its normalised criteria and final score (docs/03 §3, §5-6)."""

    candidate: Candidate
    t_hat: float  # normalised travel time (lower is better)
    b_hat: float  # normalised available-bed count (higher is better)
    c_hat: float  # capability match in [0, 1] (higher is better)
    score: float  # algorithm score (lower is better)
