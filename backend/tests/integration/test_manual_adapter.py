"""``ManualAdapter``/``GHSDataAdapter`` compare-and-set integration tests (docs/02 §3.2, FR8).

The atomicity of ``reserve``'s single ``UPDATE ... WHERE version = :expect_version`` cannot
be exercised meaningfully without a real database (SQLite has no equivalent row-level CAS
semantics under concurrent access), hence integration rather than unit. The 500-concurrent-
claims proof belongs to Increment 4's reservation manager, once fall-through exists to make
concurrent *requests* (not just concurrent adapter calls) meaningful; this file proves the
adapter-level primitive is correct in isolation.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.domain.beds.base import VersionConflict
from app.domain.beds.ghs_data_adapter import GHSDataAdapter
from app.domain.beds.manual_adapter import ManualAdapter
from app.parameters import BedType, Tier


async def _seed_facility_with_bed(
    session: AsyncSession, available: int = 4, capacity: int = 12
) -> uuid.UUID:
    facility = Facility(
        name=f"CAS Test Facility {uuid.uuid4().hex[:8]}",
        latitude="5.60",
        longitude="-0.20",
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    session.add(facility)
    await session.flush()
    session.add(
        BedCount(
            facility_id=facility.id, bed_type=BedType.ICU, available=available, capacity=capacity
        )
    )
    await session.commit()
    return facility.id


async def test_fetch_returns_current_state(db_session: AsyncSession) -> None:
    facility_id = await _seed_facility_with_bed(db_session, available=3, capacity=10)
    adapter = ManualAdapter(db_session)

    states = await adapter.fetch(facility_id)

    assert len(states) == 1
    assert states[0].bed_type == BedType.ICU
    assert states[0].available_beds == 3
    assert states[0].total_beds == 10
    assert states[0].version == 0


async def test_reserve_with_correct_version_decrements_and_bumps_version(
    db_session: AsyncSession,
) -> None:
    facility_id = await _seed_facility_with_bed(db_session, available=4)
    adapter = ManualAdapter(db_session)

    await adapter.reserve(facility_id, BedType.ICU, expect_version=0)

    [state] = await adapter.fetch(facility_id)
    assert state.available_beds == 3
    assert state.version == 1


async def test_reserve_with_stale_version_raises_version_conflict(
    db_session: AsyncSession,
) -> None:
    facility_id = await _seed_facility_with_bed(db_session, available=4)
    adapter = ManualAdapter(db_session)
    await adapter.reserve(facility_id, BedType.ICU, expect_version=0)  # version is now 1

    try:
        await adapter.reserve(facility_id, BedType.ICU, expect_version=0)  # stale
        raise AssertionError("expected VersionConflict")
    except VersionConflict:
        pass

    # The failed attempt did not mutate anything.
    [state] = await adapter.fetch(facility_id)
    assert state.available_beds == 3
    assert state.version == 1


async def test_reserve_falls_through_to_next_candidate_on_conflict(
    db_session: AsyncSession,
) -> None:
    """Simulates FR9's fall-through: a caller retries against the current version and

    succeeds, without any re-query of the candidate set — proving the CAS loop composes.
    """
    facility_id = await _seed_facility_with_bed(db_session, available=1)
    adapter = ManualAdapter(db_session)

    try:
        await adapter.reserve(facility_id, BedType.ICU, expect_version=99)
        raise AssertionError("expected VersionConflict")
    except VersionConflict:
        pass

    [state] = await adapter.fetch(facility_id)
    await adapter.reserve(facility_id, BedType.ICU, expect_version=state.version)
    [state_after] = await adapter.fetch(facility_id)
    assert state_after.available_beds == 0


async def test_reserve_on_unknown_facility_raises_version_conflict(
    db_session: AsyncSession,
) -> None:
    adapter = ManualAdapter(db_session)
    try:
        await adapter.reserve(uuid.uuid4(), BedType.ICU, expect_version=0)
        raise AssertionError("expected VersionConflict")
    except VersionConflict:
        pass


async def test_release_increments_available_capped_at_capacity(db_session: AsyncSession) -> None:
    facility_id = await _seed_facility_with_bed(db_session, available=12, capacity=12)
    adapter = ManualAdapter(db_session)

    await adapter.release(facility_id, BedType.ICU)

    [state] = await adapter.fetch(facility_id)
    assert state.available_beds == 12  # capped, not 13
    assert state.version == 0  # capped release performs no write, so no version bump


async def test_release_below_capacity_increments_version(db_session: AsyncSession) -> None:
    facility_id = await _seed_facility_with_bed(db_session, available=5, capacity=12)
    adapter = ManualAdapter(db_session)

    await adapter.release(facility_id, BedType.ICU)

    [state] = await adapter.fetch(facility_id)
    assert state.available_beds == 6
    assert state.version == 1


async def test_health_is_healthy_with_a_live_session(db_session: AsyncSession) -> None:
    adapter = ManualAdapter(db_session)
    status = await adapter.health()
    assert status.healthy is True


async def test_ghs_data_adapter_behaves_identically_over_the_same_store(
    db_session: AsyncSession,
) -> None:
    facility_id = await _seed_facility_with_bed(db_session, available=2)
    ghs = GHSDataAdapter(db_session)

    assert ghs.name() == "ghs_data"
    await ghs.reserve(facility_id, BedType.ICU, expect_version=0)

    # Reads back through ManualAdapter too — same table, same row.
    [state] = await ManualAdapter(db_session).fetch(facility_id)
    assert state.available_beds == 1
    assert state.version == 1
