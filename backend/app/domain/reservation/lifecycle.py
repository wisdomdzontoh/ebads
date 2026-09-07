"""Reservation lifecycle transitions after a bed is held (docs/01 §7, FR20, FR22, FR24-27).

Transitions a confirmed reservation can undergo:

- **arrival** (FR22): the reservation becomes permanent — nothing more to release, the
  expiry sweeper's ``WHERE NOT confirmed`` guard now excludes it.
- **acknowledgement** (FR20): records that the facility confirmed receipt, without making
  departure — or anything else — conditional on it. Advisory; never blocks anything.
- **refusal**: the facility declines the patient *at or after arrival*; the held bed is
  released back to availability via the same ``BedDataSource.release`` the expiry sweeper
  uses. Terminal — no re-allocation follows a refusal.
- **revocation** (FR24-27): the facility withdraws the reservation *before* arrival. A
  reservation is a coordination claim, not a clinical entitlement — the facility retains
  authority over its beds; the system detects the loss, tells the dispatcher, and recovers.
  Distinct from refusal precisely on that before/after-arrival line, and it is the only one
  of these four transitions that triggers **re-allocation**.
- **re-allocation** (FR24-27): re-runs the allocation engine from the dispatcher's current
  position after a revocation (or, equally, after an escalation) — same engine, a different
  origin, with the facility that just let go of the reservation excluded from the new
  candidate set.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.allocation import Allocation
from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.notification import Notification
from app.db.models.reservation import Reservation
from app.db.models.user_account import UserAccount
from app.domain.allocation.service import AllocationOutcome, AllocationRequest, AllocationService
from app.domain.audit import service as audit
from app.domain.beds.base import BedDataSource
from app.domain.notify.base import PushGateway, SMSGateway
from app.parameters import AllocationStatus, NotificationChannel, NotificationDeliveryStatus


class AllocationNotFoundError(Exception):
    """Raised when an allocation id does not exist."""


class ReservationNotFoundError(Exception):
    """Raised when a confirmed allocation has no reservation row (should not happen)."""


class AllocationNotConfirmedError(Exception):
    """Raised when arrival/acknowledgement/refusal/revocation is attempted outside the
    confirmed state."""


class AllocationAlreadyArrivedError(Exception):
    """Raised when revocation is attempted after arrival was already recorded.

    A reservation is a coordination claim, not a clinical entitlement — but once the
    patient has actually arrived, there is no claim left to withdraw. This is a distinct
    error from the generic not-confirmed case, not a silent no-op (Task 2.2).
    """


class AllocationNotReallocatableError(Exception):
    """Raised when re-allocation is attempted on an allocation that is neither revoked nor
    escalated — there is nothing to redirect from."""


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
    """The facility declines the patient at or after arrival: release the held bed, close
    the reservation. Terminal — unlike ``revoke``, this never triggers re-allocation."""
    allocation, reservation = await _load_confirmed(session, allocation_id)
    await bed_source.release(reservation.facility_id, reservation.bed_type)
    reservation.released_at = datetime.now(UTC)
    allocation.status = AllocationStatus.REFUSED
    await audit.record(
        session, actor_id, "refuse", "allocation", allocation.id, {"reason": reason}
    )
    await session.commit()
    return allocation


async def revoke(
    session: AsyncSession,
    allocation_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID,
    bed_source: BedDataSource,
    sms_gateway: SMSGateway,
    push_gateway: PushGateway,
) -> Allocation:
    """The facility withdraws the reservation before arrival (FR24-27).

    Releases the held bed via the same path the sweeper uses, then tells the dispatcher on
    both channels (push — they are a moving vehicle, not a fixed line — and SMS as the
    fallback that does not depend on an open app session). Revocation after arrival is
    refused outright, not silently absorbed as a no-op.
    """
    allocation, reservation = await _load_confirmed(session, allocation_id)
    if reservation.confirmed:
        # Already implied by the CONFIRMED-status check above (record_arrival sets both
        # fields together) — asserted directly so this can never silently no-op even if
        # that invariant is ever violated by a future write path.
        raise AllocationAlreadyArrivedError(
            f"allocation {allocation_id} already recorded arrival; cannot revoke"
        )

    await bed_source.release(reservation.facility_id, reservation.bed_type)
    reservation.revoked_at = datetime.now(UTC)
    reservation.revocation_reason = reason
    allocation.status = AllocationStatus.REVOKED
    await audit.record(
        session, actor_id, "revoke", "allocation", allocation.id, {"reason": reason}
    )

    await _notify_dispatcher_of_revocation(
        session, allocation, reservation, reason, sms_gateway, push_gateway
    )

    await session.commit()
    return allocation


async def _notify_dispatcher_of_revocation(
    session: AsyncSession,
    allocation: Allocation,
    reservation: Reservation,
    reason: str,
    sms_gateway: SMSGateway,
    push_gateway: PushGateway,
) -> None:
    """Write one Notification row per channel addressed to the dispatcher (Task 2.2).

    ``user_account`` carries no phone number or device token (docs/02 §2.3) — like
    ``LogGateway``'s own documented limitation for FR19, no real provider is integrated
    here, so the recipient string's exact format does not matter functionally. Email is the
    one identifying contact string the account actually has, so it is used for both rows.

    Looks the dispatcher up via ``allocation.request_id`` (a plain scalar column) rather
    than the ``allocation.request`` relationship, deliberately — that relationship is
    ``lazy="joined"`` and populated when ``revoke`` first loads the allocation, but nothing
    here should depend on that eager-load having happened; a second, explicit ``get`` is one
    extra round trip against the cheapest possible query, not a real cost.
    """
    emergency_request = await session.get(EmergencyRequest, allocation.request_id)
    dispatcher_id = emergency_request.dispatcher_id if emergency_request else None
    if dispatcher_id is None:
        return  # No human submitter on record (e.g. a simulation-generated request).
    dispatcher = await session.get(UserAccount, dispatcher_id)
    facility = await session.get(Facility, reservation.facility_id)
    if dispatcher is None or facility is None:
        return

    message = (
        f"EBADS: {facility.name} withdrew your reservation (reference {allocation.id}). "
        f"Reason: {reason}. Request a new recommendation from your current position."
    )
    payload = {
        "reference": str(allocation.id),
        "facility_name": facility.name,
        "reason": reason,
    }

    sms_result = await sms_gateway.send(dispatcher.email, message)
    session.add(
        Notification(
            allocation_id=allocation.id,
            channel=NotificationChannel.SMS,
            recipient=dispatcher.email,
            payload=payload,
            sent_at=datetime.now(UTC) if sms_result.delivered else None,
            delivery_status=(
                NotificationDeliveryStatus.SENT
                if sms_result.delivered
                else NotificationDeliveryStatus.FAILED
            ),
            attempts=1,
        )
    )

    push_result = await push_gateway.send(dispatcher.email, message)
    session.add(
        Notification(
            allocation_id=allocation.id,
            channel=NotificationChannel.PUSH,
            recipient=dispatcher.email,
            payload=payload,
            sent_at=datetime.now(UTC) if push_result.delivered else None,
            delivery_status=(
                NotificationDeliveryStatus.SENT
                if push_result.delivered
                else NotificationDeliveryStatus.FAILED
            ),
            attempts=1,
        )
    )


async def reallocate(
    session: AsyncSession,
    allocation_id: uuid.UUID,
    current_lat: float,
    current_lon: float,
    actor_id: uuid.UUID,
    service: AllocationService,
) -> AllocationOutcome:
    """Re-run the allocation engine from the dispatcher's current position (FR24-27).

    Valid only when the original allocation is ``revoked`` or ``escalated`` — anything else
    means there is nothing to redirect from. Same engine, a different origin (docs/01 §7);
    the urgency radius applies from ``current_lat``/``current_lon`` as-is — no elapsed-time
    deduction, since it expresses maximum acceptable *remaining* travel, not a budget. The
    facility that held (and let go of) the original reservation, if any, is excluded from
    the new candidate set so this can never send the vehicle right back to it.
    """
    original = await session.get(Allocation, allocation_id)
    if original is None:
        raise AllocationNotFoundError(str(allocation_id))
    if original.status not in (AllocationStatus.REVOKED, AllocationStatus.ESCALATED):
        raise AllocationNotReallocatableError(
            f"allocation {allocation_id} is {original.status.value}, not revoked or escalated"
        )

    # A direct fetch by request_id, not the original.request relationship — see
    # _notify_dispatcher_of_revocation's docstring for why this is deliberate, not caution.
    request = await session.get(EmergencyRequest, original.request_id)
    assert request is not None  # emergency_request.id is FK-referenced, ON DELETE CASCADE
    excluded = frozenset({original.facility_id}) if original.facility_id else frozenset()
    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=current_lat,
            patient_lon=current_lon,
            required_bed_type=request.required_bed_type,
            urgency=request.urgency,
            simulation_session_id=request.simulation_session_id,
            dispatcher_id=actor_id,
            excluded_facility_ids=excluded,
        )
    )

    assert outcome.id is not None  # allocate() always persists and assigns an id
    new_allocation = await session.get(Allocation, outcome.id)
    assert new_allocation is not None  # just persisted by the allocate() call above
    new_allocation.supersedes_allocation_id = original.id
    await audit.record(
        session,
        actor_id,
        "reallocate",
        "allocation",
        new_allocation.id,
        {"supersedes_allocation_id": str(original.id)},
    )
    await session.commit()
    return outcome
