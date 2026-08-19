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
    AllocationResponse,
    EscalatedResponse,
    FacilityBrief,
    RecommendedFacility,
    RefuseRequest,
    ReservationRead,
)
from app.config import get_settings
from app.db.models.allocation import Allocation
from app.db.models.emergency_request import EmergencyRequest
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
from app.domain.reservation import lifecycle
from app.domain.travel.base import TravelTimeService
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import AllocationStatus, PermissionAction, Status
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
FacilityStaffDep = Annotated[
    UserAccount,
    Depends(
        require_permission("allocation", PermissionAction.WRITE, trust_service_scoping=True)
    ),
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
        )
    return EscalatedResponse(
        id=outcome.id,
        nearest_within_radius=_brief(outcome.nearest_within_radius),
        nearest_available_outside_radius=_brief(outcome.nearest_available_outside_radius),
        algorithm_used=outcome.algorithm_used,
        candidates_evaluated=outcome.candidates_evaluated,
        selection_reason=outcome.selection_reason,
    )


def _to_audit_read(allocation: Allocation) -> AllocationAuditRead:
    """Assemble the read model from a joined ``Allocation`` (its ``request`` is eager-loaded)."""
    request = allocation.request
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


@router.get("/{allocation_id}", response_model=AllocationAuditRead)
async def get_allocation(
    allocation_id: uuid.UUID, session: SessionDep, actor: ReaderDep
) -> AllocationAuditRead:
    """Fetch one of the caller's own allocations by id, or ``404`` if unknown/not theirs."""
    allocation = await _get_own_allocation(session, allocation_id, actor.id)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    return _to_audit_read(allocation)


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
    return [_to_audit_read(record) for record in records]


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
    return _to_audit_read(updated)


async def _load_for_facility_actor(
    session: AsyncSession, allocation_id: uuid.UUID, actor: UserAccount
) -> Allocation:
    allocation = await session.get(Allocation, allocation_id)
    if allocation is None or allocation.facility_id != actor.facility_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    return allocation


@router.post("/{allocation_id}/acknowledge", response_model=ReservationRead)
async def acknowledge(
    allocation_id: uuid.UUID, session: SessionDep, actor: FacilityStaffDep
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
    actor: FacilityStaffDep,
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
    return _to_audit_read(updated)
