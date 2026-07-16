"""Capability-match lookup (docs/03-algorithms.md §3).

``c_hat`` is NOT min-max normalised — it is read directly from the capability matrix
``c_hat[urgency][tier]`` (docs/09 §3), which is already in [0, 1]. A ``matrix`` parameter is
accepted so the sensitivity analysis (Phase 5) can pass an alternative matrix without
touching this logic.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.parameters import CAPABILITY_MATRIX, Tier, Urgency


def capability_match(
    urgency: Urgency,
    tier: Tier,
    matrix: Mapping[Urgency, Mapping[Tier, float]] = CAPABILITY_MATRIX,
) -> float:
    """Return ``c_hat`` for an urgency/tier pair from the capability matrix."""
    return matrix[urgency][tier]
