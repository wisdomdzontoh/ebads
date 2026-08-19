"""SimulationDataSource behaviour + isolation (docs/12-testing.md §4).

Verifies the built Bridge source reads seeded per-session availability, decrements it on
allocation, raises when no bed is free, and — the isolation invariant (docs/02 §4) — never
touches ``bed_count`` / ``facility`` and keeps each session's state independent.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.db.models.simulation_bed_state import SimulationBedState
from app.db.models.simulation_session import SimulationSession
from app.domain.beds import BedUnavailableError, SimulationDataSource
from app.parameters import AlgorithmName, BedType, Tier


async def _make_facility(session: AsyncSession, name: str = "Test Hospital") -> Facility:
    facility = Facility(
        name=name,
        latitude=Decimal("5.6"),
        longitude=Decimal("-0.2"),
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    session.add(facility)
    await session.flush()
    return facility


async def _make_session(session: AsyncSession) -> SimulationSession:
    sim = SimulationSession(
        algorithm_config=AlgorithmName.URGENCY_ADAPTIVE,
        occupancy_scenario=Decimal("0.90"),
        random_seed=20260617,
        events_planned=100,
    )
    session.add(sim)
    await session.flush()
    return sim


async def _seed_bed_state(
    session: AsyncSession,
    sim: SimulationSession,
    facility: Facility,
    available: int,
    capacity: int = 10,
) -> None:
    session.add(
        SimulationBedState(
            session_id=sim.id,
            facility_id=facility.id,
            bed_type=BedType.ICU,
            available=available,
            capacity=capacity,
        )
    )
    await session.flush()


async def test_get_available_beds_reads_session_state(db_session: AsyncSession) -> None:
    facility = await _make_facility(db_session)
    sim = await _make_session(db_session)
    await _seed_bed_state(db_session, sim, facility, available=4)

    source = SimulationDataSource(db_session, sim.id)
    assert await source.get_available_beds(facility.id, BedType.ICU) == 4


async def test_get_available_beds_zero_when_untracked(db_session: AsyncSession) -> None:
    facility = await _make_facility(db_session)
    sim = await _make_session(db_session)
    # No bed-state row seeded for this session → 0 available.
    source = SimulationDataSource(db_session, sim.id)
    assert await source.get_available_beds(facility.id, BedType.ICU) == 0


async def test_allocate_decrements_available(db_session: AsyncSession) -> None:
    facility = await _make_facility(db_session)
    sim = await _make_session(db_session)
    await _seed_bed_state(db_session, sim, facility, available=2)

    source = SimulationDataSource(db_session, sim.id)
    assert await source.allocate_bed(facility.id, BedType.ICU) == 1
    assert await source.get_available_beds(facility.id, BedType.ICU) == 1


async def test_allocate_raises_when_no_bed(db_session: AsyncSession) -> None:
    facility = await _make_facility(db_session)
    sim = await _make_session(db_session)
    await _seed_bed_state(db_session, sim, facility, available=0)

    source = SimulationDataSource(db_session, sim.id)
    with pytest.raises(BedUnavailableError):
        await source.allocate_bed(facility.id, BedType.ICU)


async def test_allocation_does_not_touch_live_bed_count(db_session: AsyncSession) -> None:
    """Isolation: decrementing simulation state leaves the live bed_count unchanged."""
    facility = await _make_facility(db_session)
    db_session.add(
        BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=7, capacity=10)
    )
    sim = await _make_session(db_session)
    await _seed_bed_state(db_session, sim, facility, available=3)

    await SimulationDataSource(db_session, sim.id).allocate_bed(facility.id, BedType.ICU)

    live = await db_session.scalar(
        select(BedCount.available).where(
            BedCount.facility_id == facility.id, BedCount.bed_type == BedType.ICU
        )
    )
    assert live == 7  # the live registry is untouched by the simulation run


async def test_sessions_are_isolated_from_each_other(db_session: AsyncSession) -> None:
    """Allocating in one session does not affect another session's state for the same bed."""
    facility = await _make_facility(db_session)
    session_a = await _make_session(db_session)
    session_b = await _make_session(db_session)
    await _seed_bed_state(db_session, session_a, facility, available=3)
    await _seed_bed_state(db_session, session_b, facility, available=3)

    await SimulationDataSource(db_session, session_a.id).allocate_bed(facility.id, BedType.ICU)

    source_b = SimulationDataSource(db_session, session_b.id)
    assert await source_b.get_available_beds(facility.id, BedType.ICU) == 3
