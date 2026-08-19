"""The expiry sweeper (docs/01-architecture.md §7, FR10, S5).

Runs independently of any request, on a timer (``scripts/run_sweeper.py``,
``SWEEPER_INTERVAL_SEC``). Releases reservations whose ``expires_at`` has passed and were
never confirmed by arrival, restores availability via the bed source, marks the allocation
expired, and audits it. [IMPL] Resolves every reservation through ``ManualAdapter`` — the
live allocation path does the same (``AllocationService.allocate``'s reservation loop does
not yet resolve a bed source per-facility; see that module's notes), so this is consistent
with, not a regression from, the current reservation flow.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.allocation import Allocation
from app.db.models.reservation import Reservation
from app.domain.audit import service as audit
from app.domain.beds.manual_adapter import ManualAdapter
from app.parameters import AllocationStatus


async def sweep_once(session: AsyncSession, now: datetime | None = None) -> int:
    """Release every reservation past ``expires_at`` that was never confirmed by arrival.

    Returns the number released. Commits once at the end — one sweep cycle is one
    transaction, so a crash mid-sweep never leaves a reservation half-released.
    """
    now = now or datetime.now(UTC)
    query = select(Reservation).where(
        Reservation.released_at.is_(None),
        Reservation.confirmed.is_(False),
        Reservation.expires_at < now,
    )
    expired = list((await session.scalars(query)).all())
    if not expired:
        return 0

    adapter = ManualAdapter(session)
    for reservation in expired:
        await adapter.release(reservation.facility_id, reservation.bed_type)
        reservation.released_at = now
        allocation = await session.get(Allocation, reservation.allocation_id)
        if allocation is not None:
            allocation.status = AllocationStatus.EXPIRED
        await audit.record(
            session,
            None,  # sweeper is not a human actor (docs/02 §3.9: null for adapter-originated)
            "expire",
            "reservation",
            reservation.id,
            {"allocation_id": str(reservation.allocation_id)},
        )
    await session.commit()
    return len(expired)
