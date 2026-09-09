"""Allocation endpoints (docs/04-api-spec.md §4, docs/01 §7).

``POST /allocations`` is the core endpoint: it always returns 200 with a confirmed
reservation or a structured escalation — maps-API unavailability never errors, it falls back
to an estimated travel time (docs/04 §6). The two GET endpoints read back the persisted
decisions. ``/arrive``, ``/acknowledge``, ``/refuse`` drive the reservation lifecycle
onward (FR20, FR22).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.allocation import (
    AllocatedResponse,
    AllocationAuditRead,
    AllocationCreate,
    AllocationOverviewRead,
    AllocationResponse,
    EscalatedResponse,
    FacilityBrief,
    InboundReservationRead,
    RankedAlternative,
    ReallocateRequest,
    RecommendedFacility,
    RefuseRequest,
    ReservationRead,
    RevokeRequest,
)
from app.config import get_settings
from app.db.models.allocation import Allocation
from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.reservation import Reservation
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.domain.allocation.service import (
    AllocationOutcome,
    AllocationRequest,
    AllocationService,
    SimulationSessionNotFoundError,
)
from app.domain.allocation.service import (
    FacilityBrief as DomainFacilityBrief,
)
from app.domain.beds.manual_adapter import ManualAdapter
from app.domain.notify.log_gateway import LogGateway
from app.domain.notify.log_push_gateway import LogPushGateway
from app.domain.reservation import lifecycle
from app.domain.travel.base import TravelTimeService
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import AllocationStatus, PermissionAction, Status, Urgency
from app.security.dependencies import require_permission

router = APIRouter(prefix="/allocations", tags=["allocations"])

# Submitting and reading allocation history are both dispatcher-only (PRD §2: "submit
# emergency requests ... view own request history"); scope=all at the grant level, but the
# routes below additionally filter reads to the caller's own dispatcher_id.
DispatcherDep = Annotated[
    UserAccount, Depends(require_permission("allocation", PermissionAction.WRITE))
]
ReaderDep = Annotated[
    UserAccount, Depends(require_permission("allocation", PermissionAction.READ))
]
# own_facility grant, but facility_id is not a path param on these routes (only
# allocation_id is) — trust_service_scoping=True, with the actual match checked in the
# handler against the loaded allocation's facility_id (docs/01 §4 separation of duties).
#
# Named for what it CHECKS (the allocation:write:own_facility grant), not for which role
# happens to hold it — require_permission looks up the caller's actual role's grants, so
# this admits every role that holds the grant, not "facility_staff" specifically (it was
# previously named FacilityStaffDep, which read as role-gated when it never was; renamed
# during the role/permission audit once facility_administrator also started holding this
# same grant, 0011_allocation_grants — no functional change).
FacilityWriterDep = Annotated[
    UserAccount,
    Depends(
        require_permission("allocation", PermissionAction.WRITE, trust_service_scoping=True)
    ),
]
# Same shape as FacilityWriterDep but for the read grant (0010_facility_allocation_read,
# extended to facility_administrator by 0011) — the inbound-reservations query below filters
# by actor.facility_id itself (Task 3).
FacilityReaderDep = Annotated[
    UserAccount,
    Depends(
        require_permission("allocation", PermissionAction.READ, trust_service_scoping=True)
    ),
]
# Cross-facility, READ-ONLY oversight (role/permission audit Task 2) — gated on a resource
# name distinct from "allocation" itself (allocation_overview, 0012) specifically so this
# never admits a dispatcher, who already holds allocation:read:all for their OWN allocations
# (GET /allocations, GET /allocations/{id}) but must not see everyone else's. See that
# migration's docstring for why a new resource name, not a role check or a new scope value.
# No corresponding WRITE permission exists on this resource anywhere in the codebase — that
# absence, not a check in the route below, is what makes this endpoint structurally
# incapable of exposing acknowledge/revoke/refuse/arrive.
OverviewDep = Annotated[
    UserAccount, Depends(require_permission("allocation_overview", PermissionAction.READ))
]


def get_travel_service() -> TravelTimeService:
    """Provide the live travel-time service (Google + Haversine). Overridable in tests."""
    return LiveTravelTimeService(get_settings().google_maps_api_key)


def _allocation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    travel: Annotated[TravelTimeService, Depends(get_travel_service)],
) -> AllocationService:
    return AllocationService(session, travel)


ServiceDep = Annotated[AllocationService, Depends(_allocation_service)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _brief(brief: DomainFacilityBrief | None) -> FacilityBrief | None:
    if brief is None:
        return None
    return FacilityBrief(
        id=brief.facility_id,
        name=brief.name,
        travel_time_minutes=brief.travel_time_minutes,
        available_beds=brief.available_beds,
    )


def _to_response(outcome: AllocationOutcome) -> AllocatedResponse | EscalatedResponse:
    """Map the domain outcome onto the documented confirmed/escalated response shape."""
    assert outcome.id is not None  # set by allocate() after persistence
    if outcome.status == Status.ALLOCATED:
        # allocate() only ever returns ALLOCATED after a successful reservation — a
        # scoring win that then loses the CAS race is re-tagged ESCALATED before return
        # (AllocationService._race_exhausted_outcome), so eta_minutes is always set here.
        recommendation = outcome.recommended
        assert recommendation is not None
        assert outcome.eta_minutes is not None
        return AllocatedResponse(
            id=outcome.id,
            recommended_facility=RecommendedFacility(
                id=recommendation.facility_id,
                name=recommendation.name,
                tier=recommendation.tier,
                available_beds=recommendation.available_beds,
                travel_time_minutes=recommendation.travel_time_minutes,
                is_estimated_travel_time=recommendation.is_estimated_travel_time,
                latitude=recommendation.latitude,
                longitude=recommendation.longitude,
                contact_phone=recommendation.contact_phone,
            ),
            algorithm_used=outcome.algorithm_used,
            weight_vector=outcome.weight_vector,
            capability_match=recommendation.capability_match,
            candidates_evaluated=outcome.candidates_evaluated,
            attempts=outcome.attempts,
            eta_minutes=outcome.eta_minutes,
            selection_reason=outcome.selection_reason,
            ranked_alternatives=[
                RankedAlternative(
                    id=alt.facility_id,
                    name=alt.name,
                    tier=alt.tier,
                    available_beds=alt.available_beds,
                    travel_time_minutes=alt.travel_time_minutes,
                    is_estimated_travel_time=alt.is_estimated_travel_time,
                    capability_match=alt.capability_match,
                    score=alt.score,
                )
                for alt in outcome.ranked_alternatives
            ],
        )
    return EscalatedResponse(
        id=outcome.id,
        nearest_within_radius=_brief(outcome.nearest_within_radius),
        nearest_available_outside_radius=_brief(outcome.nearest_available_outside_radius),
        algorithm_used=outcome.algorithm_used,
        candidates_evaluated=outcome.candidates_evaluated,
        selection_reason=outcome.selection_reason,
    )


async def _to_audit_read(session: AsyncSession, allocation: Allocation) -> AllocationAuditRead:
    """Assemble the read model from a joined ``Allocation`` (its ``request`` is eager-loaded)
    plus one extra lookup for the underlying reservation's revocation reason (docs/02 §3.6) —
    there is no ORM relationship from ``allocation`` to ``reservation`` (the FK points the
    other way), and most allocations are never revoked, so a conditional query here beats
    eager-loading a row this needs on the rare status.
    """
    request = allocation.request
    revocation_reason: str | None = None
    if allocation.status == AllocationStatus.REVOKED:
        reservation = await session.scalar(
            select(Reservation).where(Reservation.allocation_id == allocation.id)
        )
        revocation_reason = reservation.revocation_reason if reservation else None
    return AllocationAuditRead(
        id=allocation.id,
        created_at=allocation.created_at,
        patient_lat=float(request.patient_lat),
        patient_lon=float(request.patient_lon),
        urgency=request.urgency,
        required_bed_type=request.required_bed_type,
        simulation_session_id=request.simulation_session_id,
        algorithm_used=allocation.strategy_used,
        weight_vector=allocation.weight_vector,
        selection_reason=allocation.selection_reason,
        facility_id=allocation.facility_id,
        travel_time_minutes=(
            float(allocation.travel_time_minutes) if allocation.travel_time_minutes else None
        ),
        is_estimated_travel_time=allocation.is_estimated_travel_time,
        eta_minutes=float(allocation.eta_minutes) if allocation.eta_minutes else None,
        capability_match=(
            float(allocation.capability_match) if allocation.capability_match else None
        ),
        candidates_evaluated=allocation.candidates_evaluated,
        attempts=allocation.attempts,
        status=allocation.status,
        supersedes_allocation_id=allocation.supersedes_allocation_id,
        revocation_reason=revocation_reason,
    )


async def _get_own_allocation(
    session: AsyncSession, allocation_id: uuid.UUID, dispatcher_id: uuid.UUID
) -> Allocation | None:
    # Allocation.request is lazy="joined" (app/db/models/allocation.py) — already eager-loaded.
    allocation = await session.get(Allocation, allocation_id)
    if allocation is None or allocation.request.dispatcher_id != dispatcher_id:
        return None
    return allocation


@router.post("", response_model=AllocationResponse)
async def create_allocation(
    payload: AllocationCreate, service: ServiceDep, actor: DispatcherDep
) -> AllocatedResponse | EscalatedResponse:
    """Submit an emergency; return a confirmed reservation or a structured escalation."""
    request = AllocationRequest(
        patient_lat=payload.patient_lat,
        patient_lon=payload.patient_lon,
        required_bed_type=payload.required_bed_type,
        urgency=payload.urgency,
        simulation_session_id=payload.simulation_session_id,
        dispatcher_id=actor.id,
    )
    try:
        outcome = await service.allocate(request)
    except SimulationSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="simulation session not found"
        ) from exc
    return _to_response(outcome)


_URGENCY_PRIORITY: dict[Urgency | None, int] = {
    Urgency.CRITICAL: 0,
    Urgency.URGENT: 1,
    Urgency.STANDARD: 2,
    None: 3,
}


def _to_inbound_read(allocation: Allocation, reservation: Reservation) -> InboundReservationRead:
    return InboundReservationRead(
        allocation_id=allocation.id,
        reservation_id=reservation.id,
        created_at=allocation.created_at,
        urgency=allocation.request.urgency,
        required_bed_type=allocation.request.required_bed_type,
        eta_minutes=float(allocation.eta_minutes) if allocation.eta_minutes else None,
        expires_at=reservation.expires_at,
        acknowledged_at=reservation.acknowledged_at,
        confirmed=reservation.confirmed,
    )


# Registered ahead of GET /{allocation_id} — a literal path segment ("inbound") must be
# matched before the parameterized route, or FastAPI tries (and fails) to parse it as a UUID.
@router.get("/inbound", response_model=list[InboundReservationRead])
async def list_inbound_reservations(
    session: SessionDep, actor: FacilityReaderDep
) -> list[InboundReservationRead]:
    """Task 3: the signed-in facility's active (confirmed) reservations, awaiting
    acknowledgement/arrival/revocation — sorted by urgency, then ETA ascending.

    ``actor.facility_id`` is ``None`` for every role but facility_staff/administrator (docs/02
    §2.3's own invariant) — the query below then matches nothing, never another facility's
    rows, so this is safe to call under any role the permission layer admits.
    """
    query = (
        select(Allocation, Reservation)
        .join(Reservation, Reservation.allocation_id == Allocation.id)
        .where(
            Allocation.facility_id == actor.facility_id,
            Allocation.status == AllocationStatus.CONFIRMED,
        )
    )
    rows = (await session.execute(query)).all()
    reads = [_to_inbound_read(allocation, reservation) for allocation, reservation in rows]
    reads.sort(
        key=lambda r: (
            _URGENCY_PRIORITY[r.urgency],
            r.eta_minutes if r.eta_minutes is not None else float("inf"),
        )
    )
    return reads


# Registered ahead of GET /{allocation_id} for the same reason as GET /inbound above — a
# literal path segment must be matched before the parameterized route.
@router.get("/overview", response_model=list[AllocationOverviewRead])
async def list_allocations_overview(
    session: SessionDep,
    actor: OverviewDep,
    status_filter: Annotated[AllocationStatus | None, Query(alias="status")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[AllocationOverviewRead]:
    """Role/permission audit Task 2: system-administrator, cross-facility, READ-ONLY
    oversight — every current allocation across every facility, newest first, with the
    facility's name attached (unlike ``list_allocations``/``get_allocation``, this caller
    doesn't already know which facility each row belongs to). Same ``status``/``from``/``to``
    filters as ``list_allocations``, which itself is left untouched — this is a dedicated
    endpoint, not a widened version of it, so a dispatcher's own scoping never changes.

    ``OverviewDep`` is the entire enforcement of "read-only": no route in this file (or
    anywhere else) can mutate an allocation under the ``allocation_overview`` permission,
    because no such grant exists for any action but ``read`` (0012). There is deliberately
    no facility_id filter here — that is the whole point of an oversight view.
    """
    query = (
        select(Allocation, Facility.name)
        .join(EmergencyRequest, Allocation.request_id == EmergencyRequest.id)
        .outerjoin(Facility, Allocation.facility_id == Facility.id)
        .order_by(Allocation.created_at.desc())
    )
    if status_filter is not None:
        query = query.where(Allocation.status == status_filter)
    if from_ is not None:
        query = query.where(Allocation.created_at >= from_)
    if to is not None:
        query = query.where(Allocation.created_at <= to)
    rows = (await session.execute(query)).all()
    reads = []
    for allocation, facility_name in rows:
        base = await _to_audit_read(session, allocation)
        reads.append(AllocationOverviewRead(**base.model_dump(), facility_name=facility_name))
    return reads


@router.get("/{allocation_id}", response_model=AllocationAuditRead)
async def get_allocation(
    allocation_id: uuid.UUID, session: SessionDep, actor: ReaderDep
) -> AllocationAuditRead:
    """Fetch one of the caller's own allocations by id, or ``404`` if unknown/not theirs."""
    allocation = await _get_own_allocation(session, allocation_id, actor.id)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    return await _to_audit_read(session, allocation)


@router.get("", response_model=list[AllocationAuditRead])
async def list_allocations(
    session: SessionDep,
    actor: ReaderDep,
    status_filter: Annotated[AllocationStatus | None, Query(alias="status")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[AllocationAuditRead]:
    """List the caller's own allocations, newest first; filter by ``status``/``from``/``to``."""
    query = (
        select(Allocation)
        .join(EmergencyRequest, Allocation.request_id == EmergencyRequest.id)
        .where(EmergencyRequest.dispatcher_id == actor.id)
        .order_by(Allocation.created_at.desc())
    )
    if status_filter is not None:
        query = query.where(Allocation.status == status_filter)
    if from_ is not None:
        query = query.where(Allocation.created_at >= from_)
    if to is not None:
        query = query.where(Allocation.created_at <= to)
    records = (await session.scalars(query)).all()
    return [await _to_audit_read(session, record) for record in records]


@router.post("/{allocation_id}/arrive", response_model=AllocationAuditRead)
async def arrive(
    allocation_id: uuid.UUID, session: SessionDep, actor: DispatcherDep
) -> AllocationAuditRead:
    """FR22: confirm the patient arrived — converts the reservation to an admission."""
    allocation = await _get_own_allocation(session, allocation_id, actor.id)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    try:
        updated = await lifecycle.record_arrival(session, allocation_id, actor.id)
    except lifecycle.AllocationNotConfirmedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except lifecycle.ReservationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no reservation on this allocation") from exc
    await session.refresh(updated, attribute_names=["request"])
    return await _to_audit_read(session, updated)


async def _load_for_facility_actor(
    session: AsyncSession, allocation_id: uuid.UUID, actor: UserAccount
) -> Allocation:
    allocation = await session.get(Allocation, allocation_id)
    if allocation is None or allocation.facility_id != actor.facility_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    return allocation


@router.post("/{allocation_id}/acknowledge", response_model=ReservationRead)
async def acknowledge(
    allocation_id: uuid.UUID, session: SessionDep, actor: FacilityWriterDep
) -> ReservationRead:
    """FR20: record facility acknowledgement — advisory, never blocks anything."""
    await _load_for_facility_actor(session, allocation_id, actor)
    try:
        reservation = await lifecycle.record_acknowledgement(session, allocation_id, actor.id)
    except lifecycle.AllocationNotConfirmedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except lifecycle.ReservationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no reservation on this allocation") from exc
    return ReservationRead.model_validate(reservation)


@router.post("/{allocation_id}/refuse", response_model=AllocationAuditRead)
async def refuse_allocation(
    allocation_id: uuid.UUID,
    payload: RefuseRequest,
    session: SessionDep,
    actor: FacilityWriterDep,
) -> AllocationAuditRead:
    """The facility declines the patient — releases the held bed back to availability."""
    await _load_for_facility_actor(session, allocation_id, actor)
    try:
        updated = await lifecycle.refuse(
            session, allocation_id, payload.reason, actor.id, ManualAdapter(session)
        )
    except lifecycle.AllocationNotConfirmedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except lifecycle.ReservationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no reservation on this allocation") from exc
    await session.refresh(updated, attribute_names=["request"])
    return await _to_audit_read(session, updated)


@router.post("/{allocation_id}/revoke", response_model=AllocationAuditRead)
async def revoke_allocation(
    allocation_id: uuid.UUID,
    payload: RevokeRequest,
    session: SessionDep,
    actor: FacilityWriterDep,
) -> AllocationAuditRead:
    """FR24-27: the facility withdraws the reservation before arrival — releases the held
    bed and notifies the dispatcher on two channels so they can request a new placement."""
    await _load_for_facility_actor(session, allocation_id, actor)
    try:
        updated = await lifecycle.revoke(
            session,
            allocation_id,
            payload.reason,
            actor.id,
            ManualAdapter(session),
            LogGateway(),
            LogPushGateway(),
        )
    except lifecycle.AllocationAlreadyArrivedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except lifecycle.AllocationNotConfirmedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except lifecycle.ReservationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no reservation on this allocation") from exc
    await session.refresh(updated, attribute_names=["request"])
    return await _to_audit_read(session, updated)


@router.post("/{allocation_id}/reallocate", response_model=AllocationResponse)
async def reallocate_allocation(
    allocation_id: uuid.UUID,
    payload: ReallocateRequest,
    service: ServiceDep,
    session: SessionDep,
    actor: DispatcherDep,
) -> AllocatedResponse | EscalatedResponse:
    """FR24-27: re-run the allocation engine from the dispatcher's current position, after
    the original reservation was revoked or the original request escalated. Same engine,
    a different origin — the revoking facility (if any) is excluded from the new candidates.
    """
    original = await _get_own_allocation(session, allocation_id, actor.id)
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    try:
        outcome = await lifecycle.reallocate(
            session, allocation_id, payload.current_lat, payload.current_lon, actor.id, service
        )
    except lifecycle.AllocationNotReallocatableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except SimulationSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="simulation session not found"
        ) from exc
    return _to_response(outcome)
