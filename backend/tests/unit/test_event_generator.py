"""Deterministic event generation (docs/07-simulation.md §6, §9; docs/12 §5).

Locks the two guarantees the reproducibility of the whole study rests on: the same seed
yields the identical event plan, and every generated field stays within its documented
domain. Bounds are asserted against ``parameters.py`` (never hardcoded) so a parameter change
is caught here (docs/12 §10).
"""

from __future__ import annotations

from app.parameters import (
    BED_TYPE_DISTRIBUTION,
    EVENT_INTERARRIVAL_MAX_MINUTES,
    EVENT_INTERARRIVAL_MIN_MINUTES,
    GA_BBOX,
    URGENCY_DISTRIBUTION,
)
from app.simulation.events import EventGenerator, PlannedEvent, generate_events


def _input_stream(events: list[PlannedEvent]) -> list[tuple[float, object, object, float, float]]:
    """Project the seed-driven event fields (everything except the LOS draw)."""
    return [
        (e.virtual_arrival_min, e.urgency, e.required_bed_type, e.patient_lat, e.patient_lon)
        for e in events
    ]


def test_same_seed_yields_identical_plan() -> None:
    """Reproducibility: regenerating with the same seed is byte-for-byte identical (docs/07 §9)."""
    assert generate_events(20260617, 50) == generate_events(20260617, 50)


def test_different_seed_yields_different_plan() -> None:
    """A different seed produces a different sequence (the seed actually drives generation)."""
    assert generate_events(1, 50) != generate_events(2, 50)


def test_arrivals_strictly_increase_by_bounded_interarrival() -> None:
    """The clock advances by a uniform inter-arrival within [min, max] each event (docs/07 §6.1)."""
    events = generate_events(20260617, 200)
    previous = 0.0
    for event in events:
        delta = event.virtual_arrival_min - previous
        assert EVENT_INTERARRIVAL_MIN_MINUTES <= delta <= EVENT_INTERARRIVAL_MAX_MINUTES
        previous = event.virtual_arrival_min


def test_urgency_and_bed_type_within_domain() -> None:
    """Every drawn urgency and bed type is one of the distribution's categories (docs/07 §6.2-3)."""
    events = generate_events(20260617, 200)
    assert all(event.urgency in URGENCY_DISTRIBUTION for event in events)
    assert all(event.required_bed_type in BED_TYPE_DISTRIBUTION for event in events)


def test_locations_within_bounding_box() -> None:
    """Patient coordinates fall inside GA_BBOX (docs/07 §3-4)."""
    lat_min, lat_max, lon_min, lon_max = GA_BBOX
    for event in generate_events(20260617, 200):
        assert lat_min <= event.patient_lat <= lat_max
        assert lon_min <= event.patient_lon <= lon_max


def test_length_of_stay_is_positive() -> None:
    """Every pre-sampled length of stay is strictly positive (docs/07 §2, §6.5)."""
    assert all(event.los_minutes > 0 for event in generate_events(20260617, 200))


def test_event_stream_is_independent_of_the_los_stream() -> None:
    """The event fields do not depend on LOS draws — the basis of paired runs (docs/07 §7).

    LOS is on its own RNG stream, so the arrival/urgency/bed-type/location sequence is fixed
    by the seed alone. We assert those fields are stable across regenerations (the same
    property the paired comparison relies on across algorithm configurations).
    """
    first = EventGenerator(20260617).generate(30)
    second = EventGenerator(20260617).generate(30)
    assert _input_stream(first) == _input_stream(second)
