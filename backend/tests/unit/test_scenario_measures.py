"""``app/scenario/measures.py`` — thesis Table 3.10 (docs/07-scenario-testing.md §6)."""

from __future__ import annotations

from app.parameters import Tier, Urgency
from app.scenario.measures import CaseResult, compute_measures, compute_measures_by_tier


def test_empty_result_set_has_zeroed_measures() -> None:
    m = compute_measures([])
    assert m.case_count == 0
    assert m.placement_success == 0.0
    assert m.escalation_rate == 0.0
    assert m.mean_travel_time_minutes is None
    assert m.mean_capability_match is None
    assert m.critical_at_tertiary_rate is None


def test_placement_success_and_escalation_rate_are_complementary() -> None:
    results = [
        CaseResult("C1", Urgency.STANDARD, True, 10.0, 0.8, Tier.PRIMARY, 1),
        CaseResult("C2", Urgency.STANDARD, False, None, None, None, 0),
        CaseResult("C3", Urgency.STANDARD, True, 20.0, 1.0, Tier.TERTIARY, 2),
        CaseResult("C4", Urgency.STANDARD, False, None, None, None, 0),
    ]
    m = compute_measures(results)
    assert m.case_count == 4
    assert m.placement_success == 0.5
    assert m.escalation_rate == 0.5
    assert m.placement_success + m.escalation_rate == 1.0


def test_travel_time_and_capability_match_average_over_allocated_only() -> None:
    results = [
        CaseResult("C1", Urgency.CRITICAL, True, 10.0, 0.6, Tier.SECONDARY, 1),
        CaseResult("C2", Urgency.CRITICAL, True, 20.0, 1.0, Tier.TERTIARY, 1),
        CaseResult("C3", Urgency.CRITICAL, False, None, None, None, 0),
    ]
    m = compute_measures(results)
    # (10 + 20) / 2, not / 3 — the escalated case must not drag the denominator down.
    assert m.mean_travel_time_minutes == 15.0
    assert m.mean_capability_match == 0.8


def test_mean_facility_attempts_averages_over_every_case() -> None:
    results = [
        CaseResult("C1", Urgency.URGENT, True, 5.0, 1.0, Tier.TERTIARY, 1),
        CaseResult("C2", Urgency.URGENT, True, 5.0, 1.0, Tier.TERTIARY, 3),
        CaseResult("C3", Urgency.URGENT, False, None, None, None, 2),
    ]
    m = compute_measures(results)
    assert m.mean_facility_attempts == 2.0


def test_critical_at_tertiary_rate_denominator_is_critical_cases_only() -> None:
    results = [
        CaseResult("C1", Urgency.CRITICAL, True, 5.0, 1.0, Tier.TERTIARY, 1),
        CaseResult("C2", Urgency.CRITICAL, True, 5.0, 0.6, Tier.SECONDARY, 1),
        CaseResult("C3", Urgency.STANDARD, True, 5.0, 1.0, Tier.TERTIARY, 1),
    ]
    m = compute_measures(results)
    # Only 1 of the 2 critical cases landed at a tertiary facility; the standard case
    # (also at a tertiary facility) must not count toward this measure at all.
    assert m.critical_at_tertiary_rate == 0.5


def test_critical_at_tertiary_rate_is_none_with_no_critical_cases() -> None:
    results = [CaseResult("C1", Urgency.STANDARD, True, 5.0, 1.0, Tier.TERTIARY, 1)]
    m = compute_measures(results)
    assert m.critical_at_tertiary_rate is None


def test_compute_measures_by_tier_splits_by_urgency() -> None:
    results = [
        CaseResult("C1", Urgency.CRITICAL, True, 5.0, 1.0, Tier.TERTIARY, 1),
        CaseResult("C2", Urgency.URGENT, False, None, None, None, 0),
        CaseResult("C3", Urgency.STANDARD, True, 30.0, 0.5, Tier.PRIMARY, 1),
    ]
    by_tier = compute_measures_by_tier(results)
    assert set(by_tier) == {Urgency.CRITICAL, Urgency.URGENT, Urgency.STANDARD}
    assert by_tier[Urgency.CRITICAL].case_count == 1
    assert by_tier[Urgency.CRITICAL].placement_success == 1.0
    assert by_tier[Urgency.URGENT].case_count == 1
    assert by_tier[Urgency.URGENT].placement_success == 0.0
    assert by_tier[Urgency.STANDARD].mean_travel_time_minutes == 30.0
