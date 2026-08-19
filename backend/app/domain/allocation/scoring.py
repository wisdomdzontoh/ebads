"""Composed scoring pipeline (docs/03-algorithms.md §1, §3, §9).

Ties together the individual steps — hard filter → normalize → capability → score → argmin —
into one deterministic function over a candidate set. This is the exact code path the
deterministic test vectors exercise (docs/12 §2) and that the allocation service and the
simulation engine both call, so simulation and live behaviour are byte-for-byte identical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.allocation.algorithms import ALGORITHMS, ScoreInputs
from app.domain.allocation.candidate import Candidate, ScoredCandidate
from app.domain.allocation.capability import capability_match
from app.domain.allocation.hard_filter import filter_candidates
from app.domain.allocation.normalization import min_max_normalize
from app.parameters import CAPABILITY_MATRIX, AlgorithmName, Tier, Urgency, WeightVector


@dataclass(frozen=True)
class ScoringResult:
    """Outcome of scoring a candidate set: the filtered set, scores, and the winner."""

    passing: list[Candidate]  # H_f, in input order
    scored: list[ScoredCandidate]
    selected: ScoredCandidate | None  # None iff H_f is empty
    weights: WeightVector | None


def _sort_key(sc: ScoredCandidate) -> tuple[float, float, str]:
    """Score, then travel time, then facility id — the documented tie-break (docs/03 §9)."""
    return (sc.score, sc.candidate.travel_time_min, sc.candidate.facility_id)


def _argmin(scored: Sequence[ScoredCandidate]) -> ScoredCandidate:
    """Pick the lowest-score candidate; tie-break by travel time, then facility id (docs/03 §9)."""
    return min(scored, key=_sort_key)


def rank_by_score(scored: Sequence[ScoredCandidate]) -> list[ScoredCandidate]:
    """Full ranking in the same deterministic order ``_argmin`` picks its winner from.

    Shared by the reservation fall-through (FR9 — try the next-ranked candidate on
    ``VersionConflict``, from this list, never a re-query) and the simulation step trace,
    so there is exactly one place the tie-break order is implemented.
    """
    return sorted(scored, key=_sort_key)


def score_candidates(
    candidates: Sequence[Candidate],
    urgency: Urgency,
    algorithm_name: AlgorithmName,
    matrix: Mapping[Urgency, Mapping[Tier, float]] = CAPABILITY_MATRIX,
    weights: WeightVector | None = None,
) -> ScoringResult:
    """Score an already-filtered candidate set ``H_f`` and choose the winner (docs/03 §3-6).

    Travel time and available beds are min-max normalised across ``H_f``; capability is
    looked up directly. Returns an empty result if ``candidates`` is empty.

    ``weights`` supplies an explicit (already-resolved) weight vector — used by the
    sensitivity analysis to score under a variant. When ``None`` (the default and every live
    call) the algorithm's own weight vector is used, so behaviour is unchanged.
    """
    if not candidates:
        return ScoringResult(passing=[], scored=[], selected=None, weights=None)

    t_hats = min_max_normalize([c.travel_time_min for c in candidates])
    b_hats = min_max_normalize([float(c.available_beds) for c in candidates])
    algorithm = ALGORITHMS[algorithm_name]
    weights = weights if weights is not None else algorithm.weight_vector(urgency)

    scored: list[ScoredCandidate] = []
    for candidate, t_hat, b_hat in zip(candidates, t_hats, b_hats, strict=True):
        c_hat = capability_match(urgency, candidate.tier, matrix)
        inputs = ScoreInputs(
            t_hat=t_hat, b_hat=b_hat, c_hat=c_hat, travel_time_min=candidate.travel_time_min
        )
        score = algorithm.score(inputs, weights)
        scored.append(
            ScoredCandidate(candidate=candidate, t_hat=t_hat, b_hat=b_hat, c_hat=c_hat, score=score)
        )

    return ScoringResult(
        passing=list(candidates), scored=scored, selected=_argmin(scored), weights=weights
    )


def run_scoring(
    candidates: Sequence[Candidate],
    urgency: Urgency,
    radius_minutes: float,
    algorithm_name: AlgorithmName,
    matrix: Mapping[Urgency, Mapping[Tier, float]] = CAPABILITY_MATRIX,
    weights: WeightVector | None = None,
) -> ScoringResult:
    """Apply the hard filter then score the survivors (docs/03 §1-6).

    ``matrix`` and ``weights`` allow a sensitivity variant's capability matrix and weight
    vector to be supplied; both default to the ``parameters.py`` configuration.
    """
    filtered = filter_candidates(candidates, radius_minutes)
    return score_candidates(filtered, urgency, algorithm_name, matrix, weights)
