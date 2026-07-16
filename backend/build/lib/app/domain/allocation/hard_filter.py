"""Hard filter and escalation fallbacks (docs/03-algorithms.md §2).

The hard filter keeps only candidates that are both reachable within the urgency radius and
have at least one available bed:  ``H_f = { h : beds(h,β) >= 1 AND t(p,h) <= R(u) }``.
When ``H_f`` is empty the engine escalates with two informational fallbacks rather than
routing to an unreachable or full facility.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.allocation.candidate import Candidate


def passes_hard_filter(candidate: Candidate, radius_minutes: float) -> bool:
    """Return True if the candidate has a free bed and is within the urgency radius."""
    return candidate.available_beds >= 1 and candidate.travel_time_min <= radius_minutes


def filter_candidates(candidates: Sequence[Candidate], radius_minutes: float) -> list[Candidate]:
    """Return ``H_f``: the candidates passing the hard filter (docs/03 §2)."""
    return [c for c in candidates if passes_hard_filter(c, radius_minutes)]


def _nearest(candidates: Sequence[Candidate]) -> Candidate | None:
    """Return the shortest-travel candidate, breaking ties by facility id; None if empty."""
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c.travel_time_min, c.facility_id))


def escalation_fallbacks(
    candidates: Sequence[Candidate], radius_minutes: float
) -> tuple[Candidate | None, Candidate | None]:
    """Compute the two escalation fallbacks (docs/03 §2).

    Returns ``(nearest_within_radius, nearest_available_outside_radius)``:
      - nearest within radius, ignoring beds;
      - nearest with an available bed but outside the radius.
    Either may be None (no such facility); both None is valid.
    """
    within_radius = [c for c in candidates if c.travel_time_min <= radius_minutes]
    available_outside = [
        c for c in candidates if c.available_beds >= 1 and c.travel_time_min > radius_minutes
    ]
    return _nearest(within_radius), _nearest(available_outside)
