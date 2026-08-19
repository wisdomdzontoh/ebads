"""Expiry sweeper integration tests (docs/01 §7, FR10, S5).

Verifies a reservation past ``expires_at`` is released within one sweep cycle: the bed
returns to availability, the allocation is marked expired, and a confirmed (arrived)
reservation is left alone regardless of its expiry time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.allocation import Allocation
from app.db.models.bed_count import BedCount
from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.reservation import Reservation
from app.domain.sweeper.service import sweep_once
from app.parameters import AlgorithmName, AllocationStatus, BedType, Tier, Urgency


async def _seed_confirmed_allocation(
    session: AsyncSession, *, expires_at: datetime, confirmed: bool = False
) -> tuple[Facility, Allocation, Reservation]:
    facility = Facility(
        name="Sweeper Test Facility",
        latitude="5.60",
        longitude="-0.20",
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    session.add(facility)
    await session.flush()
    session.add(BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=3, capacity=4))

    request = EmergencyRequest(
        patient_lat="5.60",
        patient_lon="-0.20",
        urgency=Urgency.CRITICAL,
        required_bed_type=BedType.ICU,
    )
    session.add(request)
    await session.flush()

    allocation = Allocation(
        request_id=request.id,
        facility_id=facility.id,
        strategy_used=AlgorithmName.URGENCY_ADAPTIVE,
        candidates_evaluated=1,
        attempts=1,
        selection_reason="test",
        status=AllocationStatus.CONFIRMED,
    )
    session.add(allocation)
    await session.flush()

    reservation = Reservation(
        allocation_id=allocation.id,
        facility_id=facility.id,
        bed_type=BedType.ICU,
        created_at=datetime.now(UTC) - timedelta(minutes=30),
        expires_at=expires_at,
        confirmed=confirmed,
    )
    session.add(reservation)
    await session.commit()
    return facility, allocation, reservation


async def test_sweep_releases_an_expired_reservation(db_session: AsyncSession) -> None:
    _facility, allocation, reservation = await _seed_confirmed_allocation(
        db_session, expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    released = await sweep_once(db_session)

    assert released == 1
    await db_session.refresh(reservation)
    await db_session.refresh(allocation)
    assert reservation.released_at is not None
    assert allocation.status == AllocationStatus.EXPIRED


async def test_sweep_restores_bed_availability(db_session: AsyncSession) -> None:
    facility, _allocation, _reservation = await _seed_confirmed_allocation(
        db_session, expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    before = await db_session.scalar(
        select(BedCount).where(BedCount.facility_id == facility.id)
    )
    assert before is not None
    available_before = before.available
    version_before = before.version

    await sweep_once(db_session)

    after = await db_session.scalar(select(BedCount).where(BedCount.facility_id == facility.id))
    assert after is not None
    assert after.available == available_before + 1
    assert after.version == version_before + 1


async def test_sweep_leaves_unexpired_reservations_alone(db_session: AsyncSession) -> None:
    await _seed_confirmed_allocation(
        db_session, expires_at=datetime.now(UTC) + timedelta(minutes=30)
    )
    released = await sweep_once(db_session)
    assert released == 0


async def test_sweep_never_releases_a_confirmed_arrival(db_session: AsyncSession) -> None:
    """A reservation whose arrival was already recorded is exempt regardless of expires_at."""
    _facility, allocation, reservation = await _seed_confirmed_allocation(
        db_session, expires_at=datetime.now(UTC) - timedelta(minutes=1), confirmed=True
    )
    allocation.status = AllocationStatus.ARRIVED
    await db_session.commit()

    released = await sweep_once(db_session)

    assert released == 0
    await db_session.refresh(reservation)
    assert reservation.released_at is None


async def test_sweep_is_idempotent_within_one_cycle(db_session: AsyncSession) -> None:
    await _seed_confirmed_allocation(
        db_session, expires_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    first = await sweep_once(db_session)
    second = await sweep_once(db_session)
    assert first == 1
    assert second == 0  # already released — released_at excludes it from the next sweep
