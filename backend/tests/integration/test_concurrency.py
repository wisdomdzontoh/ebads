"""FR8/S1 — the thesis's central correctness claim: zero double-allocation under concurrency.

"A concurrency test shows zero double-allocation under 500 simultaneous claims on one bed
... Repeat 20x, zero violations." Each claim is a separate DB session issuing
``ManualAdapter.reserve`` with the *same* ``expect_version`` (what every claimant would have
read from an advisory ``fetch`` before racing) — the single atomic
``UPDATE ... WHERE version = :expect_version`` (``domain/beds/manual_adapter.py``) is what
must make exactly one of the 500 win, however many actually run at once.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.domain.beds.base import VersionConflict
from app.domain.beds.manual_adapter import ManualAdapter
from app.parameters import BedType, Tier
from tests.integration.conftest import TEST_DATABASE_URL

_CLAIMANTS = 500
# Bounded pool: enough concurrent DB connections for a genuine race, safely under Postgres's
# default connection limit (~100) even with other fixtures/sessions active in the suite.
_POOL_SIZE = 20
_MAX_OVERFLOW = 20


async def _seed_single_bed(session: AsyncSession) -> uuid.UUID:
    """Register one facility with exactly one available ICU bed; return the facility id."""
    facility = Facility(
        name=f"Concurrency Test Facility {uuid.uuid4().hex}",
        latitude="5.60",
        longitude="-0.20",
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    session.add(facility)
    await session.flush()
    session.add(BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=1, capacity=1))
    await session.commit()
    return facility.id


async def _claim(
    sessionmaker: async_sessionmaker[AsyncSession], facility_id: uuid.UUID
) -> bool:
    """One claimant's attempt: True if it won the reservation, False on VersionConflict.

    ``reserve`` only flushes — commit is deliberately the caller's job (the same contract
    live callers rely on, so a caller can add the allocation/reservation rows to the same
    transaction). Skipping it here would roll the UPDATE back on session close, releasing
    the row lock and letting the next claimant see the same stale version — every claim
    would then "succeed" against an isolated, discarded transaction. Committing is what
    makes this a real test of cross-transaction contention.
    """
    async with sessionmaker() as session:
        try:
            await ManualAdapter(session).reserve(facility_id, BedType.ICU, expect_version=0)
        except VersionConflict:
            return False
        await session.commit()
        return True


async def _run_one_repetition(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as seed_session:
        facility_id = await _seed_single_bed(seed_session)

    results = await asyncio.gather(
        *(_claim(sessionmaker, facility_id) for _ in range(_CLAIMANTS))
    )

    wins = sum(results)
    assert wins == 1, f"expected exactly 1 success among {_CLAIMANTS} claims, got {wins}"

    async with sessionmaker() as check_session:
        bed = await check_session.scalar(
            select(BedCount).where(BedCount.facility_id == facility_id)
        )
        assert bed is not None
        assert bed.available == 0  # decremented exactly once, not 500 times
        assert bed.version == 1  # incremented exactly once


@pytest.mark.parametrize("repetition", range(20))
async def test_500_concurrent_claims_yield_exactly_one_success(
    repetition: int, db_session: AsyncSession
) -> None:
    """FR8/S1, repeated 20x per the accept criterion — each repetition is a fresh bed.

    ``db_session`` is depended on only for its truncate-on-setup side effect (a clean
    schema before the first repetition); the test drives its own pooled engine below so
    the 500 claimants get genuinely concurrent connections, not one shared session (which
    SQLAlchemy's AsyncSession does not support across concurrent coroutines).
    """
    engine = create_async_engine(
        TEST_DATABASE_URL, pool_size=_POOL_SIZE, max_overflow=_MAX_OVERFLOW
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _run_one_repetition(sessionmaker)
    finally:
        await engine.dispose()
