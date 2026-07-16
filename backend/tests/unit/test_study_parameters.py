"""Per-study scoring parameters (docs/09 §10, docs/08 §4).

Verifies that the defaults reproduce ``parameters.py``, that overrides merge onto the defaults
(only stated values change), that ``weight_for`` resolves per algorithm/urgency, and that a
malformed variant is rejected by the same load-time rules as the defaults (docs/09 §12).
"""

from __future__ import annotations

import pytest

from app.domain.allocation.study_parameters import StudyParameters, from_overrides
from app.parameters import (
    ALGORITHM_2_WEIGHTS,
    ALGORITHM_3_WEIGHTS,
    CAPABILITY_MATRIX,
    RADIUS_MINUTES,
    AlgorithmName,
    ParameterValidationError,
    Tier,
    Urgency,
)


def test_defaults_match_parameters_module() -> None:
    """The default bundle equals the parameters.py configuration."""
    params = StudyParameters.defaults()
    assert params.radius_minutes == RADIUS_MINUTES
    assert params.capability_matrix == CAPABILITY_MATRIX
    assert params.weights_weighted == ALGORITHM_2_WEIGHTS
    assert params.weights_urgency_adaptive == ALGORITHM_3_WEIGHTS


def test_weight_for_resolves_per_algorithm_and_urgency() -> None:
    """Greedy → None; Weighted → fixed; Urgency-Adaptive → per-urgency (docs/03 §4-6)."""
    params = StudyParameters.defaults()
    assert params.weight_for(AlgorithmName.GREEDY, Urgency.CRITICAL) is None
    assert params.weight_for(AlgorithmName.WEIGHTED, Urgency.CRITICAL) == ALGORITHM_2_WEIGHTS
    assert (
        params.weight_for(AlgorithmName.URGENCY_ADAPTIVE, Urgency.CRITICAL)
        == ALGORITHM_3_WEIGHTS[Urgency.CRITICAL]
    )


def test_capability_override_merges_only_stated_cells() -> None:
    """The steeper-critical variant changes only the critical row; other rows keep defaults."""
    params = from_overrides(
        capability_config={"critical": {"tertiary": 1.0, "secondary": 0.4, "primary": 0.1}}
    )
    assert params.capability_matrix[Urgency.CRITICAL][Tier.SECONDARY] == 0.4
    assert params.capability_matrix[Urgency.CRITICAL][Tier.PRIMARY] == 0.1
    # Untouched rows still equal the defaults.
    assert params.capability_matrix[Urgency.URGENT] == CAPABILITY_MATRIX[Urgency.URGENT]
    assert params.capability_matrix[Urgency.STANDARD] == CAPABILITY_MATRIX[Urgency.STANDARD]


def test_weight_override_merges_urgency_adaptive_rows() -> None:
    """A weight variant overrides the stated urgency rows and validates sum-to-one."""
    params = from_overrides(
        weight_config={"urgency_adaptive": {"critical": {"w_t": 0.6, "w_b": 0.1, "w_c": 0.3}}}
    )
    critical = params.weights_urgency_adaptive[Urgency.CRITICAL]
    assert (critical.w_t, critical.w_b, critical.w_c) == (0.6, 0.1, 0.3)
    # Unstated rows keep their defaults.
    assert params.weights_urgency_adaptive[Urgency.URGENT] == ALGORITHM_3_WEIGHTS[Urgency.URGENT]


def test_radius_override_merges() -> None:
    """A radius variant overrides stated urgencies; the rest keep defaults."""
    params = from_overrides(radius_config={"critical": 20, "standard": 120})
    assert params.radius_minutes[Urgency.CRITICAL] == 20
    assert params.radius_minutes[Urgency.URGENT] == RADIUS_MINUTES[Urgency.URGENT]
    assert params.radius_minutes[Urgency.STANDARD] == 120


def test_weight_override_rejects_non_unit_sum() -> None:
    """A weight vector that does not sum to 1.0 is rejected at construction (docs/09 §12)."""
    with pytest.raises(ValueError, match="sum to 1.0"):
        from_overrides(
            weight_config={"urgency_adaptive": {"critical": {"w_t": 0.9, "w_b": 0.9, "w_c": 0.9}}}
        )


def test_non_monotonic_radius_variant_is_rejected() -> None:
    """A variant violating R(critical) ≤ R(urgent) ≤ R(standard) is rejected (docs/09 §12.4)."""
    with pytest.raises(ParameterValidationError, match="monotonic|R\\(critical\\)"):
        from_overrides(radius_config={"critical": 90, "standard": 30})


def test_out_of_range_capability_variant_is_rejected() -> None:
    """A capability value outside [0, 1] is rejected (docs/09 §12.3)."""
    with pytest.raises(ParameterValidationError, match="outside"):
        from_overrides(capability_config={"critical": {"tertiary": 1.5}})
