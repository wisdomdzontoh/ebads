"""AllocationService at the service layer (docs/01 §3.3, docs/03 §8).

Exercises the simulation path end-to-end: a request carrying a ``simulation_session_id`` must
run the session's configured algorithm and read availability from the session's isolated
``simulation_bed_state`` (not the live ``bed_count``).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.db.models.simulation_bed_state import SimulationBedState
from app.db.models.simulation_session import SimulationSession
from app.domain.allocation.service import AllocationRequest, AllocationService
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.parameters import AlgorithmName, BedType, Status, Tier, Urgency


class _StubTravel(TravelTimeService):
    """Fixed in-radius travel time so the test isolates algorithm + bed-source behaviour."""

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=5.0, is_estimated=False)


async def _make_icu_facility(session: AsyncSession) -> Facility:
    facility = Facility(
        name="Sim Hospital",
        latitude=Decimal("5.6"),
        longitude=Decimal("-0.2"),
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    session.add(facility)
    await session.flush()
    return facility


async def test_simulation_request_uses_session_algorithm_and_isolated_beds(
    db_session: AsyncSession,
) -> None:
    facility = await _make_icu_facility(db_session)
    # Live registry says NO icu beds...
    db_session.add(
        BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=0, capacity=10)
    )
    # ...but this simulation session's isolated state has 2.
    sim = SimulationSession(
        algorithm_config=AlgorithmName.WEIGHTED,
        occupancy_scenario=Decimal("0.90"),
        random_seed=20260617,
        events_planned=100,
    )
    db_session.add(sim)
    await db_session.flush()
    db_session.add(
        SimulationBedState(
            session_id=sim.id,
            facility_id=facility.id,
            bed_type=BedType.ICU,
            available=2,
            capacity=10,
        )
    )
    await db_session.flush()

    service = AllocationService(db_session, _StubTravel())
    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=5.6,
            patient_lon=-0.2,
            required_bed_type=BedType.ICU,
            urgency=Urgency.CRITICAL,  # live would pick urgency_adaptive; session forces weighted
            simulation_session_id=sim.id,
        )
    )

    # Selector honoured the session's configured algorithm, not the urgency default.
    assert outcome.algorithm_used == AlgorithmName.WEIGHTED
    # Allocated (not escalated) proves it read the session's beds, not the empty live registry.
    assert outcome.status == Status.ALLOCATED
    assert outcome.recommended is not None
    assert outcome.recommended.facility_id == facility.id


async def test_live_request_escalates_when_local_beds_empty(db_session: AsyncSession) -> None:
    facility = await _make_icu_facility(db_session)
    db_session.add(
        BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=0, capacity=10)
    )
    await db_session.flush()

    service = AllocationService(db_session, _StubTravel())
    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=5.6,
            patient_lon=-0.2,
            required_bed_type=BedType.ICU,
            urgency=Urgency.CRITICAL,
        )
    )

    assert outcome.status == Status.ESCALATED
    assert outcome.algorithm_used == AlgorithmName.URGENCY_ADAPTIVE
    assert outcome.nearest_within_radius is not None
    assert outcome.nearest_within_radius.facility_id == facility.id
