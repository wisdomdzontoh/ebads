"""Per-run metric definitions (docs/07-simulation.md §8, docs/12 §5).

Hand-computed cases pin the four metrics to their documented denominators: ATBP averages
only allocated events, FRR counts escalations over all events, MCEE averages
``candidates_evaluated`` over all events (escalations contribute their 0), and CM averages
capability over allocated events with a critical-only variant. Empty-set means are ``None``.
"""

from __future__ import annotations

from app.parameters import Status, Urgency
from app.simulation.metrics import EventMetricRow, compute_run_metrics


def _allocated(
    urgency: Urgency, candidates: int, placement: float, capability: float
) -> EventMetricRow:
    return EventMetricRow(Status.ALLOCATED, candidates, urgency, placement, capability)


def _escalated(urgency: Urgency) -> EventMetricRow:
    return EventMetricRow(Status.ESCALATED, 0, urgency, None, None)


def test_metrics_use_the_correct_denominators() -> None:
    """A mixed run: verify each metric against its by-hand value (docs/07 §8)."""
    events = [
        _allocated(Urgency.CRITICAL, candidates=5, placement=12.0, capability=1.0),
        _allocated(Urgency.STANDARD, candidates=3, placement=8.0, capability=0.5),
        _escalated(Urgency.URGENT),
    ]
    metrics = compute_run_metrics(events)

    assert metrics.atbp == (12.0 + 8.0) / 2  # allocated only
    assert metrics.frr == 1 / 3  # one escalation of three events
    assert metrics.mcee == (5 + 3 + 0) / 3  # over all events, escalation contributes 0
    assert metrics.cm == (1.0 + 0.5) / 2  # allocated only
    assert metrics.cm_critical == 1.0  # the single allocated critical event
    assert (metrics.events_total, metrics.events_allocated, metrics.events_escalated) == (3, 2, 1)


def test_all_escalated_gives_undefined_means_as_none() -> None:
    """When nothing is allocated, ATBP / CM / critical-CM are None, not a fabricated 0.0."""
    metrics = compute_run_metrics([_escalated(Urgency.CRITICAL), _escalated(Urgency.STANDARD)])
    assert metrics.atbp is None
    assert metrics.cm is None
    assert metrics.cm_critical is None
    assert metrics.frr == 1.0
    assert metrics.mcee == 0.0


def test_critical_cm_isolates_critical_allocations() -> None:
    """CM (critical) averages capability over allocated *critical* events only (docs/07 §8)."""
    events = [
        _allocated(Urgency.CRITICAL, candidates=4, placement=10.0, capability=1.0),
        _allocated(Urgency.CRITICAL, candidates=4, placement=10.0, capability=0.6),
        _allocated(Urgency.STANDARD, candidates=4, placement=10.0, capability=0.2),
    ]
    metrics = compute_run_metrics(events)
    assert metrics.cm == (1.0 + 0.6 + 0.2) / 3
    assert metrics.cm_critical == (1.0 + 0.6) / 2


def test_empty_run_is_all_zero_and_none() -> None:
    """A run with no events yields zero counts and undefined (None) means."""
    metrics = compute_run_metrics([])
    assert metrics.events_total == 0
    assert metrics.frr == 0.0 and metrics.mcee == 0.0
    assert metrics.atbp is None and metrics.cm is None and metrics.cm_critical is None
