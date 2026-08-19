"""Reservation lifecycle transitions after a bed is held (docs/01 §7, FR20, FR22).

Three transitions a confirmed reservation can undergo, each terminal except acknowledgement
(which is advisory and never blocks anything — FR20):

- **arrival** (FR22): the reservation becomes permanent — nothing more to release, the
  expiry sweeper's ``WHERE NOT confirmed`` guard now excludes it.
- **acknowledgement** (FR20): records that the facility confirmed receipt, without making
  departure — or anything else — conditional on it.
- **refusal**: the facility declines the patient; the held bed is released back to
  availability via the same ``BedDataSource.release`` the expiry sweeper uses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.allocation import Allocation
from app.db.models.reservation import Reservation
from app.domain.audit import service as audit
from app.domain.beds.base import BedDataSource
from app.parameters import AllocationStatus


class AllocationNotFoundError(Exception):
    """Raised when an allocation id does not exist."""


class ReservationNotFoundError(Exception):
    """Raised when a confirmed allocation has no reservation row (should not happen)."""


class AllocationNotConfirmedError(Exception):
    """Raised when arrival/acknowledgement/refusal is attempted outside the confirmed state."""


async def _load_confirmed(
    session: AsyncSession, allocation_id: uuid.UUID
) -> tuple[Allocation, Reservation]:
    allocation = await session.get(Allocation, allocation_id)
    if allocation is None:
        raise AllocationNotFoundError(str(allocation_id))
    reservation = await session.scalar(
        select(Reservation).where(Reservation.allocation_id == allocation_id)
    )
    if reservation is None:
        raise ReservationNotFoundError(str(allocation_id))
    if allocation.status != AllocationStatus.CONFIRMED:
        raise AllocationNotConfirmedError(
            f"allocation {allocation_id} is {allocation.status.value}, not confirmed"
        )
    return allocation, reservation


async def record_arrival(
    session: AsyncSession, allocation_id: uuid.UUID, actor_id: uuid.UUID
) -> Allocation:
    """FR22: convert a confirmed reservation to an admission.

    The bed was already decremented at reservation time (docs/01 §7 step 3) — arrival marks
    the hold permanent, it does not decrement again. ``reservation.confirmed = true`` is
    what "arrival recorded" means on that table (docs/02 §3.6); it also removes the
    reservation from the sweeper's ``WHERE NOT confirmed`` scan.
    """
    allocation, reservation = await _load_confirmed(session, allocation_id)
    allocation.status = AllocationStatus.ARRIVED
    reservation.confirmed = True
    await audit.record(session, actor_id, "arrive", "allocation", allocation.id)
    await session.commit()
    return allocation


async def record_acknowledgement(
    session: AsyncSession, allocation_id: uuid.UUID, actor_id: uuid.UUID
) -> Reservation:
    """FR20: record facility acknowledgement — advisory, never blocks anything."""
    _, reservation = await _load_confirmed(session, allocation_id)
    reservation.acknowledged_at = datetime.now(UTC)
    await audit.record(session, actor_id, "acknowledge", "reservation", reservation.id)
    await session.commit()
    return reservation


async def refuse(
    session: AsyncSession,
    allocation_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID,
    bed_source: BedDataSource,
) -> Allocation:
    """The facility declines the patient: release the held bed, close the reservation."""
    allocation, reservation = await _load_confirmed(session, allocation_id)
    await bed_source.release(reservation.facility_id, reservation.bed_type)
    reservation.released_at = datetime.now(UTC)
    allocation.status = AllocationStatus.REFUSED
    await audit.record(
        session, actor_id, "refuse", "allocation", allocation.id, {"reason": reason}
    )
    await session.commit()
    return allocation
