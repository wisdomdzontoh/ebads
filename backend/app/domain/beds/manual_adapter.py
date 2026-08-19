"""``ManualAdapter`` — portal-entered bed counts held in ``bed_state`` (docs/01 §5, built, default).

The default bed source: it reads and reserves against the availability maintained via
``PATCH /facilities/{id}/beds`` and seeded by the facility loader. ``reserve``/``release``
are atomic compare-and-set updates against ``bed_count.version`` — the only place in the
codebase that mutates ``available`` outside the manual-maintenance endpoint, and it always
increments ``version`` in the same statement (docs/02 §3.2 invariant).

``updated_by`` is left null on adapter-driven writes (docs/02 §3.2: "null when written by
an adapter") — attribution to a human belongs to the ``PATCH .../beds`` path
(``domain/facilities/service.py``), not here.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.db.models.bed_count import BedCount
from app.domain.beds.base import BedDataSource, BedState, HealthStatus, VersionConflict
from app.parameters import BedType


class ManualAdapter(BedDataSource):
    """Live bed availability from the local ``bed_count`` registry (docs/02 §3.2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def name(self) -> str:
        return "manual"

    async def fetch(self, facility_id: uuid.UUID) -> list[BedState]:
        rows = (
            await self._session.scalars(
                select(BedCount).where(BedCount.facility_id == facility_id)
            )
        ).all()
        return [
            BedState(
                facility_id=row.facility_id,
                bed_type=row.bed_type,
                total_beds=row.capacity,
                available_beds=row.available,
                version=row.version,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    async def reserve(
        self, facility_id: uuid.UUID, bed_type: BedType, expect_version: int
    ) -> None:
        """Decrement ``available`` iff the row is still at ``expect_version`` and has a free bed.

        A single ``UPDATE ... WHERE version = :expect_version AND available > 0`` is the
        entire compare-and-set: zero rows affected means either someone else already wrote
        this row (version moved) or it never existed — both are ``VersionConflict`` (see the
        exception's docstring). Since ``available`` only ever changes together with
        ``version`` (this method and ``release`` are the sole writers to both, in the same
        statement), a version match can never coincide with ``available == 0``: whichever
        caller last set this version observed a free bed at that moment. There is no
        "matched version but no bed" case to distinguish.
        """
        # UPDATE always yields a CursorResult (rowcount available); the ORM-generic Result
        # type execute() returns statically doesn't expose it, hence the cast.
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                update(BedCount)
                .where(
                    BedCount.facility_id == facility_id,
                    BedCount.bed_type == bed_type,
                    BedCount.version == expect_version,
                    BedCount.available > 0,
                )
                .values(
                    available=BedCount.available - 1,
                    version=BedCount.version + 1,
                    updated_at=func.now(),
                )
            ),
        )
        if result.rowcount == 0:
            raise VersionConflict(
                f"reserve failed: facility {facility_id} bed_type {bed_type.value} is not "
                f"at version {expect_version} (or does not exist)"
            )
        await self._session.flush()

    async def release(self, facility_id: uuid.UUID, bed_type: BedType) -> None:
        """Increment ``available`` (capped at ``capacity``). Best-effort — see the ABC docstring."""
        await self._session.execute(
            update(BedCount)
            .where(
                BedCount.facility_id == facility_id,
                BedCount.bed_type == bed_type,
                BedCount.available < BedCount.capacity,
            )
            .values(
                available=BedCount.available + 1,
                version=BedCount.version + 1,
                updated_at=func.now(),
            )
        )
        await self._session.flush()

    async def health(self) -> HealthStatus:
        """Healthy iff the existing DB session can round-trip a trivial query."""
        try:
            await self._session.execute(select(1))
        except DBAPIError as exc:
            return HealthStatus(healthy=False, detail=str(exc))
        return HealthStatus(healthy=True)
