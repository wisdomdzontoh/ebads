"""Min-max normalization across the candidate set (docs/03-algorithms.md §3).

Each criterion (travel time, available-bed count) is min-max normalised across the *current*
filtered set ``H_f``. The documented tie rule (docs/09 §6): when every value is equal
(``x_max == x_min``), each normalised value is ``NORMALIZATION_TIE_VALUE`` (0.5) instead of a
divide-by-zero.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.parameters import NORMALIZATION_TIE_VALUE


def min_max_normalize(values: Sequence[float]) -> list[float]:
    """Return the min-max normalised values; all-equal inputs map to the tie value (0.5)."""
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high == low:
        return [NORMALIZATION_TIE_VALUE] * len(values)
    span = high - low
    return [(value - low) / span for value in values]
