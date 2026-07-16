"""Per-run simulation metrics (docs/07-simulation.md §8, thesis §3.13.1).

Four metrics summarise one run; the per-run means are the unit of statistical analysis
(n = 30 per configuration per scenario). All four are computed here from the event records so
the definitions live in exactly one place:

- **ATBP** — mean ``time_to_bed_placement_min`` over *allocated* events (escalated excluded).
- **FRR**  — fraction of events that escalated (hard filter left ``H_f`` empty).
- **MCEE** — mean ``candidates_evaluated`` over *all* events (escalations contribute 0).
- **CM**   — mean ``capability_match`` over allocated events; also reported for critical-only.

Means over an empty set (e.g. ATBP when every event escalated) are ``None`` rather than a
fabricated 0.0 — an undefined mean must not masquerade as a real measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.parameters import Status, Urgency


@dataclass(frozen=True)
class EventMetricRow:
    """The subset of one event's fields the metrics need (decouples metrics from the ORM)."""

    status: Status
    candidates_evaluated: int
    urgency: Urgency
    time_to_bed_placement_min: float | None
    capability_match: float | None


@dataclass(frozen=True)
class RunMetrics:
    """The four thesis metrics for one run, plus the counts they were computed from."""

    atbp: float | None
    frr: float
    mcee: float
    cm: float | None
    cm_critical: float | None
    events_total: int
    events_allocated: int
    events_escalated: int


def _mean(values: Sequence[float]) -> float | None:
    """Arithmetic mean, or ``None`` for an empty sequence (an undefined mean, not 0.0)."""
    return sum(values) / len(values) if values else None


def compute_run_metrics(events: Sequence[EventMetricRow]) -> RunMetrics:
    """Compute ATBP / FRR / MCEE / CM (+ critical-only CM) for one run (docs/07 §8)."""
    total = len(events)
    if total == 0:
        return RunMetrics(None, 0.0, 0.0, None, None, 0, 0, 0)

    allocated = [event for event in events if event.status == Status.ALLOCATED]
    escalated = [event for event in events if event.status == Status.ESCALATED]
    critical_allocated = [event for event in allocated if event.urgency == Urgency.CRITICAL]

    placement_times = [
        event.time_to_bed_placement_min
        for event in allocated
        if event.time_to_bed_placement_min is not None
    ]
    capabilities = [
        event.capability_match for event in allocated if event.capability_match is not None
    ]
    critical_capabilities = [
        event.capability_match
        for event in critical_allocated
        if event.capability_match is not None
    ]

    return RunMetrics(
        atbp=_mean(placement_times),
        frr=len(escalated) / total,
        mcee=sum(event.candidates_evaluated for event in events) / total,
        cm=_mean(capabilities),
        cm_critical=_mean(critical_capabilities),
        events_total=total,
        events_allocated=len(allocated),
        events_escalated=len(escalated),
    )
