"""Tests for the parameters module (docs/12-testing.md; acceptance for docs/15 Phase 0).

Two responsibilities:
  1. The real, shipped configuration satisfies every docs/09 §12 invariant.
  2. The validation machinery actually REJECTS malformed configurations — a weight row
     that does not sum to 1.0, an out-of-range capability, non-monotonic radii, the wrong
     occupancy set, or a distribution that does not sum to 1.0.

Per docs/12 §10 these tests assert structural invariants (sums, ranges, monotonicity)
rather than hardcoding the literal numbers, so they stay correct if a researcher revises a
value in parameters.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.parameters import (
    ALGORITHM_2_WEIGHTS,
    ALGORITHM_3_WEIGHTS,
    BED_TYPE_DISTRIBUTION,
    CAPABILITY_MATRIX,
    OCCUPANCY_SCENARIOS,
    RADIUS_MINUTES,
    SUM_TOLERANCE,
    URGENCY_DISTRIBUTION,
    ParameterValidationError,
    Tier,
    Urgency,
    WeightVector,
    _validate_capability_in_range,
    _validate_distribution,
    _validate_occupancy_scenarios,
    _validate_radius_monotonic,
    validate_parameters,
)

# --- the shipped configuration is valid ------------------------------------


def test_shipped_parameters_validate() -> None:
    """The real configuration passes all §12 checks (it ran once at import; re-run here)."""
    validate_parameters()


def test_algorithm_2_weights_sum_to_one() -> None:
    w = ALGORITHM_2_WEIGHTS
    assert abs(w.w_t + w.w_b + w.w_c - 1.0) <= SUM_TOLERANCE


@pytest.mark.parametrize("urgency", list(Urgency))
def test_algorithm_3_weight_rows_sum_to_one(urgency: Urgency) -> None:
    w = ALGORITHM_3_WEIGHTS[urgency]
    assert abs(w.w_t + w.w_b + w.w_c - 1.0) <= SUM_TOLERANCE


def test_every_urgency_has_a_radius_and_weight_row() -> None:
    """Coverage guard: no urgency is missing a radius or an Algorithm 3 weight row."""
    for urgency in Urgency:
        assert urgency in RADIUS_MINUTES
        assert urgency in ALGORITHM_3_WEIGHTS


# --- WeightVector rejects bad triples (docs/09 §12.1-2) --------------------


def test_weight_vector_rejects_non_unit_sum() -> None:
    with pytest.raises(ValidationError):
        WeightVector(w_t=0.4, w_b=0.4, w_c=0.4)  # sums to 1.2


def test_weight_vector_accepts_unit_sum() -> None:
    w = WeightVector(w_t=0.5, w_b=0.15, w_c=0.35)
    assert abs(w.w_t + w.w_b + w.w_c - 1.0) <= SUM_TOLERANCE


# --- capability range (docs/09 §12.3) --------------------------------------


def test_capability_validator_rejects_out_of_range() -> None:
    bad = {Urgency.CRITICAL: {Tier.TERTIARY: 1.5, Tier.SECONDARY: 0.6, Tier.PRIMARY: 0.2}}
    with pytest.raises(ParameterValidationError):
        _validate_capability_in_range(bad)


def test_shipped_capability_in_range() -> None:
    _validate_capability_in_range(CAPABILITY_MATRIX)


# --- radius monotonicity (docs/09 §12.4) -----------------------------------


def test_radius_validator_rejects_non_monotonic() -> None:
    # critical wider than urgent violates R(critical) <= R(urgent) <= R(standard).
    bad = {Urgency.CRITICAL: 90, Urgency.URGENT: 60, Urgency.STANDARD: 30}
    with pytest.raises(ParameterValidationError):
        _validate_radius_monotonic(bad)


# --- occupancy set (docs/09 §12.5) -----------------------------------------


def test_occupancy_validator_rejects_wrong_set() -> None:
    with pytest.raises(ParameterValidationError):
        _validate_occupancy_scenarios((0.5, 0.9, 1.0))


def test_shipped_occupancy_is_exact_set() -> None:
    _validate_occupancy_scenarios(OCCUPANCY_SCENARIOS)


# --- distributions sum to one (docs/09 §12.6) ------------------------------


def test_distribution_validator_rejects_non_unit_sum() -> None:
    with pytest.raises(ParameterValidationError):
        _validate_distribution({Urgency.CRITICAL: 0.2, Urgency.URGENT: 0.2}, "broken")


@pytest.mark.parametrize(
    ("distribution", "label"),
    [(URGENCY_DISTRIBUTION, "urgency"), (BED_TYPE_DISTRIBUTION, "bed-type")],
)
def test_shipped_distributions_sum_to_one(distribution: dict[object, float], label: str) -> None:
    _validate_distribution(distribution, label)
