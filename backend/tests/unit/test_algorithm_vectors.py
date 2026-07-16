"""Deterministic algorithm vectors — the core safety net (docs/12-testing.md §2).

Each JSON in ``tests/vectors/`` fixes a candidate set + request and the *independently
computed* expected normalised values, per-candidate scores, and selected facility. This one
parametrized test recomputes everything through the real scoring pipeline and asserts exact
agreement (within 1e-9). A drift between the implementation and the documented formulas
fails here and blocks merge.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.domain.allocation.candidate import Candidate
from app.domain.allocation.hard_filter import escalation_fallbacks
from app.domain.allocation.scoring import run_scoring
from app.parameters import AlgorithmName, Tier, Urgency

VECTOR_DIR = pathlib.Path(__file__).resolve().parents[1] / "vectors"
VECTOR_FILES = sorted(VECTOR_DIR.glob("*.json"))

# 1e-9 equality tolerance (docs/12 §2).
TOL = 1e-9


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidates(vector: dict) -> list[Candidate]:
    return [
        Candidate(
            facility_id=c["id"],
            tier=Tier(c["tier"]),
            travel_time_min=float(c["travel_min"]),
            available_beds=int(c["beds"]),
        )
        for c in vector["candidates"]
    ]


def test_vector_directory_is_non_empty() -> None:
    """Guard against the glob silently finding nothing."""
    assert VECTOR_FILES, f"no vectors found in {VECTOR_DIR}"


@pytest.mark.parametrize("path", VECTOR_FILES, ids=lambda p: p.stem)
def test_algorithm_vector(path: pathlib.Path) -> None:
    vector = _load(path)
    candidates = _candidates(vector)
    urgency = Urgency(vector["request"]["urgency"])
    algorithm = AlgorithmName(vector["algorithm"])
    radius = float(vector["radius_minutes"])
    expected = vector["expected"]

    result = run_scoring(candidates, urgency, radius, algorithm)

    # Hard filter: exactly the expected candidates survive.
    assert [c.facility_id for c in result.passing] == expected["passes_hard_filter"]

    if expected["selected"] is None:
        # Escalation case: no winner; verify the two documented fallbacks.
        assert result.selected is None
        within, outside = escalation_fallbacks(candidates, radius)
        within_id = within.facility_id if within else None
        outside_id = outside.facility_id if outside else None
        assert within_id == expected["escalation"]["nearest_within_radius"]
        assert outside_id == expected["escalation"]["nearest_available_outside_radius"]
        return

    # Scoring case: normalised values, weights, scores, and the winner all match.
    by_id = {sc.candidate.facility_id: sc for sc in result.scored}
    for fid, sc in by_id.items():
        assert sc.t_hat == pytest.approx(expected["t_hat"][fid], abs=TOL)
        assert sc.b_hat == pytest.approx(expected["b_hat"][fid], abs=TOL)
        assert sc.c_hat == pytest.approx(expected["c_hat"][fid], abs=TOL)
        assert sc.score == pytest.approx(expected["score"][fid], abs=TOL)

    if expected["weights"] is None:
        assert result.weights is None  # greedy carries no weight vector
    else:
        assert result.weights is not None
        assert result.weights.w_t == pytest.approx(expected["weights"]["w_t"], abs=TOL)
        assert result.weights.w_b == pytest.approx(expected["weights"]["w_b"], abs=TOL)
        assert result.weights.w_c == pytest.approx(expected["weights"]["w_c"], abs=TOL)

    assert result.selected is not None
    assert result.selected.candidate.facility_id == expected["selected"]
