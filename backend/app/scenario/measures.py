"""Scenario measures — thesis Table 3.10 (docs/07-scenario-testing.md §6, FR23).

Six measures, each computed overall and disaggregated by urgency tier — an aggregate mean
would conceal exactly the differentiation the urgency-adaptive strategy is designed to
produce (docs/07 §6). Every function here is a pure aggregation over already-decided
:class:`CaseResult` rows; nothing here re-runs or re-scores anything.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.parameters import Tier, Urgency


@dataclass(frozen=True)
class CaseResult:
    """The recorded outcome of replaying one case (docs/07 §6's raw material).

    ``attempts`` is the number of reservation attempts the CAS fall-through made before
    succeeding (or exhausting every candidate) — 0 on an escalation with no candidate to
    attempt at all, matching ``AllocationOutcome.attempts``'s own convention.
    """

    case_id: str
    urgency: Urgency
    allocated: bool
    travel_time_minutes: float | None
    capability_match: float | None
    tier: Tier | None
    attempts: int


@dataclass(frozen=True)
class MeasureSet:
    """One row of thesis Table 3.10, already reduced to the documented denominators."""

    case_count: int
    placement_success: float
    escalation_rate: float
    mean_facility_attempts: float
    mean_travel_time_minutes: float | None
    mean_capability_match: float | None
    critical_at_tertiary_rate: float | None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def compute_measures(results: Sequence[CaseResult]) -> MeasureSet:
    """Reduce a set of case results to the six thesis Table 3.10 measures.

    Denominators follow docs/07 §6 exactly: travel time and capability match average over
    allocated cases only; critical-at-tertiary averages over critical cases only; placement
    success, escalation rate, and facility attempts average over every case.
    """
    if not results:
        return MeasureSet(
            case_count=0,
            placement_success=0.0,
            escalation_rate=0.0,
            mean_facility_attempts=0.0,
            mean_travel_time_minutes=None,
            mean_capability_match=None,
            critical_at_tertiary_rate=None,
        )

    allocated = [r for r in results if r.allocated]
    critical = [r for r in results if r.urgency == Urgency.CRITICAL]
    critical_at_tertiary = [r for r in critical if r.allocated and r.tier == Tier.TERTIARY]

    return MeasureSet(
        case_count=len(results),
        placement_success=len(allocated) / len(results),
        escalation_rate=(len(results) - len(allocated)) / len(results),
        mean_facility_attempts=_mean([float(r.attempts) for r in results]) or 0.0,
        mean_travel_time_minutes=_mean(
            [r.travel_time_minutes for r in allocated if r.travel_time_minutes is not None]
        ),
        mean_capability_match=_mean(
            [r.capability_match for r in allocated if r.capability_match is not None]
        ),
        critical_at_tertiary_rate=(
            len(critical_at_tertiary) / len(critical) if critical else None
        ),
    )


def compute_measures_by_tier(
    results: Sequence[CaseResult],
) -> dict[Urgency, MeasureSet]:
    """``compute_measures``, disaggregated by urgency tier (docs/07 §6: "every measure...")."""
    return {
        urgency: compute_measures([r for r in results if r.urgency == urgency])
        for urgency in Urgency
    }
