"""Normalization tie rule, tie-break order, and the M(u) regression guard (docs/12 §2)."""

from __future__ import annotations

from app.domain.allocation.candidate import Candidate, ScoredCandidate
from app.domain.allocation.normalization import min_max_normalize
from app.domain.allocation.scoring import _argmin, run_scoring
from app.parameters import NORMALIZATION_TIE_VALUE, AlgorithmName, Tier, Urgency


def _candidate(fid: str, tier: Tier, travel: float, beds: int) -> Candidate:
    return Candidate(facility_id=fid, tier=tier, travel_time_min=travel, available_beds=beds)


def test_normalization_tie_rule_all_equal() -> None:
    """All-equal values collapse to 0.5 rather than dividing by zero (docs/09 §6)."""
    assert min_max_normalize([7.0, 7.0, 7.0]) == [NORMALIZATION_TIE_VALUE] * 3


def test_tiebreak_prefers_shorter_travel_then_id() -> None:
    """Equal scores -> shorter travel wins; equal travel -> lower facility id (docs/03 §9)."""
    a = ScoredCandidate(_candidate("A", Tier.TERTIARY, 12, 1), 0.0, 0.0, 1.0, score=0.5)
    b = ScoredCandidate(_candidate("B", Tier.TERTIARY, 8, 1), 0.0, 0.0, 1.0, score=0.5)
    assert _argmin([a, b]).candidate.facility_id == "B"  # shorter travel

    c = ScoredCandidate(_candidate("C", Tier.TERTIARY, 8, 1), 0.0, 0.0, 1.0, score=0.5)
    assert _argmin([c, b]).candidate.facility_id == "B"  # equal score+travel -> id "B" < "C"


def test_mu_regression_guard_algo3_differs_from_algo2() -> None:
    """Urgency-adaptive must select a DIFFERENT facility than weighted on the same set.

    Proves urgency is encoded in the weight vector and genuinely changes the argmin — not the
    rejected scalar ``M(u)·Score2`` formulation, which cannot (docs/03 §6, docs/12 §2).
    Critical: weighted (w_b=0.35) favours the bed-rich primary X; urgency-adaptive
    (w_c=0.35) favours the high-capability tertiary Y.
    """
    candidates = [
        _candidate("X", Tier.PRIMARY, travel=10, beds=10),
        _candidate("Y", Tier.TERTIARY, travel=10, beds=2),
    ]
    weighted = run_scoring(candidates, Urgency.CRITICAL, 30, AlgorithmName.WEIGHTED)
    adaptive = run_scoring(candidates, Urgency.CRITICAL, 30, AlgorithmName.URGENCY_ADAPTIVE)

    assert weighted.selected is not None and adaptive.selected is not None
    assert weighted.selected.candidate.facility_id == "X"
    assert adaptive.selected.candidate.facility_id == "Y"
    assert weighted.selected.candidate.facility_id != adaptive.selected.candidate.facility_id
