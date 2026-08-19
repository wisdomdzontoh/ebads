"""Simulation engine + session lifecycle against a real DB (docs/12-testing.md §5).

Covers occupancy seeding, that a run persists per-event records and leaves the live registry
untouched (isolation), reproducibility (same seed → identical events), the bed-release
mechanism, and the run-once state guard. A fixed in-radius stub travel service is used so the
assertions isolate engine behaviour from travel-time details (the matrix is tested in unit).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.db.models.simulation_allocation_event import SimulationAllocationEvent
from app.db.models.simulation_bed_state import SimulationBedState
from app.db.models.simulation_session import SimulationSession
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.parameters import AlgorithmName, BedType, Status, Tier, Urgency
from app.simulation.engine import SimulationEngine
from app.simulation.service import (
    SessionConfig,
    SimulationService,
    SimulationSessionStateError,
)

_ALL_BED_TYPES = [BedType.GENERAL, BedType.ICU, BedType.MATERNITY_SPECIALIST]


class _StubTravel(TravelTimeService):
    """Fixed, in-radius travel time so allocations are deterministic in engine tests."""

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=5.0, is_estimated=False)


async def _make_facility(
    session: AsyncSession, name: str = "Sim Hospital", capacity: int = 12
) -> Facility:
    facility = Facility(
        name=name,
        latitude=Decimal("5.60"),
        longitude=Decimal("-0.20"),
        tier=Tier.TERTIARY,
        supported_bed_types=list(_ALL_BED_TYPES),
        contact_phone="+233000000000",
    )
    session.add(facility)
    await session.flush()
    for bed_type in _ALL_BED_TYPES:
        session.add(
            BedCount(
                facility_id=facility.id, bed_type=bed_type, available=capacity, capacity=capacity
            )
        )
    await session.commit()
    return facility


def _event_fields(record: SimulationAllocationEvent) -> tuple[object, ...]:
    """The full comparable tuple of one event, for reproducibility equality."""
    return (
        record.event_index,
        record.virtual_arrival_min,
        record.urgency,
        record.required_bed_type,
        record.patient_lat,
        record.patient_lon,
        record.status,
        record.recommended_facility_id,
        record.travel_time_minutes,
        record.time_to_bed_placement_min,
        record.capability_match,
        record.candidates_evaluated,
        record.los_minutes,
        record.bed_release_virtual_min,
    )


async def test_occupancy_seeding_available_equals_round_capacity_times_free(
    db_session: AsyncSession,
) -> None:
    """Seeded available = round(capacity·(1−occupancy)); 0 at 100% occupancy (docs/07 §4)."""
    facility = await _make_facility(db_session, capacity=12)
    service = SimulationService(db_session, _StubTravel())

    partial = await service.create_session(
        SessionConfig(AlgorithmName.WEIGHTED, 0.75, events_planned=5, random_seed=1)
    )
    full = await service.create_session(
        SessionConfig(AlgorithmName.WEIGHTED, 1.00, events_planned=5, random_seed=1)
    )

    partial_icu = await db_session.scalar(
        select(SimulationBedState.available).where(
            SimulationBedState.session_id == partial.id,
            SimulationBedState.facility_id == facility.id,
            SimulationBedState.bed_type == BedType.ICU,
        )
    )
    full_icu = await db_session.scalar(
        select(SimulationBedState.available).where(
            SimulationBedState.session_id == full.id,
            SimulationBedState.facility_id == facility.id,
            SimulationBedState.bed_type == BedType.ICU,
        )
    )
    assert partial_icu == round(12 * (1.0 - 0.75))  # == 3
    assert full_icu == 0


async def test_run_persists_events_and_leaves_live_registry_untouched(
    db_session: AsyncSession,
) -> None:
    """A run writes one record per event, allocates some, and never mutates bed_count."""
    facility = await _make_facility(db_session, capacity=12)
    service = SimulationService(db_session, _StubTravel())
    sim = await service.create_session(
        SessionConfig(AlgorithmName.WEIGHTED, 0.75, events_planned=8, random_seed=20260617)
    )

    metrics = await service.run_session(sim.id)
    events = await service.get_events(sim.id)

    assert [event.event_index for event in events] == list(range(8))
    assert metrics.events_total == 8
    assert metrics.events_allocated >= 1  # in-radius stub + seeded beds => some placements
    # Isolation: the live bed_count is unchanged by the simulation run (docs/02 §4).
    live = await db_session.scalars(
        select(BedCount.available).where(BedCount.facility_id == facility.id)
    )
    assert set(live.all()) == {12}


async def test_same_seed_reproduces_identical_events(db_session: AsyncSession) -> None:
    """Two sessions with the same seed/config produce identical per-event outcomes (docs/07 §9)."""
    await _make_facility(db_session, capacity=12)
    service = SimulationService(db_session, _StubTravel())

    first = await service.create_session(
        SessionConfig(AlgorithmName.URGENCY_ADAPTIVE, 0.90, events_planned=10, random_seed=777)
    )
    await service.run_session(first.id)
    second = await service.create_session(
        SessionConfig(AlgorithmName.URGENCY_ADAPTIVE, 0.90, events_planned=10, random_seed=777)
    )
    await service.run_session(second.id)

    first_events = [_event_fields(e) for e in await service.get_events(first.id)]
    second_events = [_event_fields(e) for e in await service.get_events(second.id)]
    assert first_events == second_events


async def test_due_bed_release_returns_bed_to_pool(db_session: AsyncSession) -> None:
    """A held bed whose LOS elapsed by time t is returned to the pool (docs/07 §2)."""
    facility = await _make_facility(db_session, capacity=1)
    sim = SimulationSession(
        algorithm_config=AlgorithmName.WEIGHTED,
        occupancy_scenario=Decimal("1.00"),
        random_seed=1,
        events_planned=5,
    )
    db_session.add(sim)
    await db_session.flush()
    # The bed is currently held (available 0 of capacity 1) by an earlier allocated event.
    db_session.add(
        SimulationBedState(
            session_id=sim.id,
            facility_id=facility.id,
            bed_type=BedType.ICU,
            available=0,
            capacity=1,
        )
    )
    db_session.add(
        SimulationAllocationEvent(
            session_id=sim.id,
            event_index=0,
            virtual_arrival_min=Decimal("10"),
            urgency=Urgency.CRITICAL,
            required_bed_type=BedType.ICU,
            patient_lat=Decimal("5.60"),
            patient_lon=Decimal("-0.20"),
            recommended_facility_id=facility.id,
            travel_time_minutes=Decimal("5"),
            time_to_bed_placement_min=Decimal("10"),
            capability_match=Decimal("1.0"),
            candidates_evaluated=1,
            status=Status.ALLOCATED,
            los_minutes=Decimal("10"),
            bed_release_virtual_min=Decimal("20"),
        )
    )
    await db_session.flush()

    engine = SimulationEngine(sim, db_session, _StubTravel())
    await engine._apply_due_releases(Decimal("25"))  # 25 > release(20) → freed

    available = await db_session.scalar(
        select(SimulationBedState.available).where(SimulationBedState.session_id == sim.id)
    )
    assert available == 1


async def test_bed_not_released_before_its_los_elapses(db_session: AsyncSession) -> None:
    """A bed is not returned before its release time (docs/07 §2)."""
    facility = await _make_facility(db_session, capacity=1)
    sim = SimulationSession(
        algorithm_config=AlgorithmName.WEIGHTED,
        occupancy_scenario=Decimal("1.00"),
        random_seed=1,
        events_planned=5,
    )
    db_session.add(sim)
    await db_session.flush()
    db_session.add(
        SimulationBedState(
            session_id=sim.id,
            facility_id=facility.id,
            bed_type=BedType.ICU,
            available=0,
            capacity=1,
        )
    )
    db_session.add(
        SimulationAllocationEvent(
            session_id=sim.id,
            event_index=0,
            virtual_arrival_min=Decimal("10"),
            urgency=Urgency.CRITICAL,
            required_bed_type=BedType.ICU,
            patient_lat=Decimal("5.60"),
            patient_lon=Decimal("-0.20"),
            recommended_facility_id=facility.id,
            travel_time_minutes=Decimal("5"),
            time_to_bed_placement_min=Decimal("10"),
            capability_match=Decimal("1.0"),
            candidates_evaluated=1,
            status=Status.ALLOCATED,
            los_minutes=Decimal("40"),
            bed_release_virtual_min=Decimal("50"),
        )
    )
    await db_session.flush()

    engine = SimulationEngine(sim, db_session, _StubTravel())
    await engine._apply_due_releases(Decimal("15"))  # 15 < release(50) → still held

    available = await db_session.scalar(
        select(SimulationBedState.available).where(SimulationBedState.session_id == sim.id)
    )
    assert available == 0


async def test_running_a_completed_session_is_a_state_error(db_session: AsyncSession) -> None:
    """Re-running a session that already has events is rejected (maps to HTTP 409, docs/04 §6)."""
    await _make_facility(db_session, capacity=12)
    service = SimulationService(db_session, _StubTravel())
    sim = await service.create_session(
        SessionConfig(AlgorithmName.GREEDY, 0.75, events_planned=3, random_seed=5)
    )
    await service.run_session(sim.id)
    with pytest.raises(SimulationSessionStateError):
        await service.run_session(sim.id)
