"""Deterministic synthetic event generation (docs/07-simulation.md §6).

An ``EventGenerator`` turns a session's ``random_seed`` into a fixed sequence of
``PlannedEvent``s — arrival time on the virtual clock, urgency, required bed type, patient
location, and a pre-sampled length of stay. The whole plan is a pure function of the seed:
regenerating with the same seed yields byte-identical events, which is the foundation of the
reproducibility guarantee (docs/07 §9).

Two independent RNG streams are used (docs/07 §7): the *event* stream draws arrival deltas,
urgency, bed type, and location; the *length-of-stay* stream draws LOS. Keeping LOS on its
own stream — and pre-sampling a LOS for every event regardless of whether it is ultimately
allocated — means the generated sequence is identical across algorithm configurations at a
given seed. That is what lets the evaluation pair runs and use paired statistical tests
(docs/07 §7, docs/08). Whether a bed is actually held (and thus whether the LOS is *used*)
is decided later by the engine, not here.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.parameters import (
    BED_TYPE_DISTRIBUTION,
    EVENT_INTERARRIVAL_MAX_MINUTES,
    EVENT_INTERARRIVAL_MIN_MINUTES,
    GA_BBOX,
    LOS_MEAN_MINUTES,
    LOS_RANDOM_STREAM_OFFSET,
    URGENCY_DISTRIBUTION,
    BedType,
    Urgency,
)


@dataclass(frozen=True)
class PlannedEvent:
    """One synthetic emergency, fully determined before the engine sees it (docs/07 §6)."""

    event_index: int
    virtual_arrival_min: float
    urgency: Urgency
    required_bed_type: BedType
    patient_lat: float
    patient_lon: float
    # Pre-sampled length of stay; the engine uses it only if this event is allocated.
    los_minutes: float


def _weighted_choice[T](rng: random.Random, distribution: Mapping[T, float]) -> T:
    """Draw one key from ``distribution`` (values are probabilities summing to 1.0).

    Iterates the mapping in its fixed definition order and walks the cumulative weight, so
    the draw is deterministic for a given RNG state. The distributions are validated to sum
    to 1.0 at import (``parameters.validate_parameters``); the final key is returned as a
    safety net against floating-point drift at the tail.
    """
    threshold = rng.random()
    cumulative = 0.0
    items = list(distribution.items())
    for key, probability in items:
        cumulative += probability
        if threshold < cumulative:
            return key
    return items[-1][0]


class EventGenerator:
    """Generates the deterministic event plan for one simulation session (docs/07 §6)."""

    def __init__(
        self,
        seed: int,
        bbox: tuple[float, float, float, float] = GA_BBOX,
    ) -> None:
        self._seed = seed
        self._bbox = bbox

    def generate(self, events_planned: int) -> list[PlannedEvent]:
        """Produce the full, ordered event plan for the session.

        Fresh RNGs are constructed from the seed on every call, so the method is idempotent:
        the same ``(seed, events_planned)`` always yields the identical list.
        """
        event_rng = random.Random(self._seed)
        los_rng = random.Random(self._seed + LOS_RANDOM_STREAM_OFFSET)
        lat_min, lat_max, lon_min, lon_max = self._bbox

        events: list[PlannedEvent] = []
        clock = 0.0
        for index in range(events_planned):
            # Draw order is fixed (docs/07 §6.1-6.4); changing it would change every plan.
            clock += event_rng.uniform(
                EVENT_INTERARRIVAL_MIN_MINUTES, EVENT_INTERARRIVAL_MAX_MINUTES
            )
            urgency = _weighted_choice(event_rng, URGENCY_DISTRIBUTION)
            bed_type = _weighted_choice(event_rng, BED_TYPE_DISTRIBUTION)
            patient_lat = event_rng.uniform(lat_min, lat_max)
            patient_lon = event_rng.uniform(lon_min, lon_max)
            los_minutes = los_rng.expovariate(1.0 / LOS_MEAN_MINUTES[bed_type])
            events.append(
                PlannedEvent(
                    event_index=index,
                    virtual_arrival_min=clock,
                    urgency=urgency,
                    required_bed_type=bed_type,
                    patient_lat=patient_lat,
                    patient_lon=patient_lon,
                    los_minutes=los_minutes,
                )
            )
        return events


def generate_events(seed: int, events_planned: int) -> Sequence[PlannedEvent]:
    """Convenience wrapper: the deterministic event plan for ``seed`` (docs/07 §6)."""
    return EventGenerator(seed).generate(events_planned)
