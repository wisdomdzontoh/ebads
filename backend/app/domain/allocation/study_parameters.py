"""Per-study scoring parameters — defaults, or a sensitivity variant (docs/09 §10, docs/08 §4).

The allocation pipeline normally reads the radii, capability matrix, and weight vectors
straight from ``parameters.py``. The sensitivity analysis (Phase 5) re-runs the grid under
*variants* of exactly those values, so this bundle lets a run carry an alternative set without
touching the module constants. ``StudyParameters.defaults()`` reproduces the ``parameters.py``
configuration bit-for-bit, so threading this bundle everywhere changes nothing for the main
grid; a variant is supplied only by the sensitivity driver.

Override dicts (from ``config/sensitivity.yaml``) are *merged* onto the defaults — a variant
need only state the values it changes (docs/09 §10: "other rows as agreed") — and the result
is validated against the same load-time rules as the defaults (docs/09 §12), so a malformed
variant fails loudly instead of silently scoring with a bad configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.parameters import (
    ALGORITHM_2_WEIGHTS,
    ALGORITHM_3_WEIGHTS,
    CAPABILITY_MATRIX,
    RADIUS_MINUTES,
    AlgorithmName,
    ParameterValidationError,
    Tier,
    Urgency,
    WeightVector,
)


@dataclass(frozen=True)
class StudyParameters:
    """The radii, capability matrix, and weight vectors in effect for one run (docs/09)."""

    radius_minutes: Mapping[Urgency, int]
    capability_matrix: Mapping[Urgency, Mapping[Tier, float]]
    weights_weighted: WeightVector
    weights_urgency_adaptive: Mapping[Urgency, WeightVector]

    @classmethod
    def defaults(cls) -> StudyParameters:
        """The ``parameters.py`` configuration — identical to the un-overridden pipeline."""
        return cls(
            radius_minutes=dict(RADIUS_MINUTES),
            capability_matrix={u: dict(row) for u, row in CAPABILITY_MATRIX.items()},
            weights_weighted=ALGORITHM_2_WEIGHTS,
            weights_urgency_adaptive=dict(ALGORITHM_3_WEIGHTS),
        )

    def weight_for(
        self, algorithm_name: AlgorithmName, urgency: Urgency
    ) -> WeightVector | None:
        """Resolve the weight vector for an algorithm + urgency (None for Greedy — docs/03 §4)."""
        if algorithm_name == AlgorithmName.GREEDY:
            return None
        if algorithm_name == AlgorithmName.WEIGHTED:
            return self.weights_weighted
        return self.weights_urgency_adaptive[urgency]


def _merge_radius(override: Mapping[str, Any] | None) -> dict[Urgency, int]:
    """Merge a radius override onto the defaults (missing urgencies keep their default)."""
    radius = dict(RADIUS_MINUTES)
    for key, value in (override or {}).items():
        radius[Urgency(key)] = int(value)
    return radius


def _merge_capability(
    override: Mapping[str, Any] | None,
) -> dict[Urgency, dict[Tier, float]]:
    """Merge a capability override onto the defaults, row by row and tier by tier."""
    matrix = {u: dict(row) for u, row in CAPABILITY_MATRIX.items()}
    for urgency_key, row in (override or {}).items():
        for tier_key, value in row.items():
            matrix[Urgency(urgency_key)][Tier(tier_key)] = float(value)
    return matrix


def _merge_weights(
    override: Mapping[str, Any] | None,
) -> tuple[WeightVector, dict[Urgency, WeightVector]]:
    """Merge a weight override onto the defaults (Algorithm 2 vector + Algorithm 3 per-urgency)."""
    override = override or {}
    weighted = ALGORITHM_2_WEIGHTS
    if "weighted" in override:
        weighted = WeightVector(**override["weighted"])  # sum-to-1 enforced on construction
    adaptive = dict(ALGORITHM_3_WEIGHTS)
    for urgency_key, vector in override.get("urgency_adaptive", {}).items():
        adaptive[Urgency(urgency_key)] = WeightVector(**vector)
    return weighted, adaptive


def _validate(params: StudyParameters) -> None:
    """Re-assert the docs/09 §12 rules on a variant (capability ∈ [0,1]; radius monotonic)."""
    for urgency, row in params.capability_matrix.items():
        for tier, value in row.items():
            if not 0.0 <= value <= 1.0:
                raise ParameterValidationError(
                    f"variant capability[{urgency}][{tier}] = {value!r} is outside [0, 1]"
                )
    radius = params.radius_minutes
    if not radius[Urgency.CRITICAL] <= radius[Urgency.URGENT] <= radius[Urgency.STANDARD]:
        raise ParameterValidationError(
            "variant radius must satisfy R(critical) <= R(urgent) <= R(standard)"
        )


def from_overrides(
    radius_config: Mapping[str, Any] | None = None,
    capability_config: Mapping[str, Any] | None = None,
    weight_config: Mapping[str, Any] | None = None,
) -> StudyParameters:
    """Build validated :class:`StudyParameters` by merging overrides onto the defaults."""
    weighted, adaptive = _merge_weights(weight_config)
    params = StudyParameters(
        radius_minutes=_merge_radius(radius_config),
        capability_matrix=_merge_capability(capability_config),
        weights_weighted=weighted,
        weights_urgency_adaptive=adaptive,
    )
    _validate(params)
    return params
