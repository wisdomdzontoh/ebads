"""Allocation endpoints (docs/04-api-spec.md §4).

``POST /allocations`` is the core endpoint: it always returns 200 with a recommendation or a
structured escalation — maps-API unavailability never errors, it falls back to an estimated
travel time (docs/04 §6). The two GET endpoints read back the persisted audit records.
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
)
from app.config import get_settings
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
from app.domain.travel.base import TravelTimeService
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import PermissionAction, Status
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
    """Map the domain outcome onto the documented allocated/escalated response shape."""
    assert outcome.id is not None  # set by allocate() after persistence
    if outcome.status == Status.ALLOCATED:
        recommendation = outcome.recommended
        assert recommendation is not None
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


@router.post("", response_model=AllocationResponse)
async def create_allocation(
    payload: AllocationCreate, service: ServiceDep, actor: DispatcherDep
) -> AllocatedResponse | EscalatedResponse:
    """Submit an emergency; return a recommendation or a structured escalation (docs/04 §4)."""
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
    """Fetch one of the caller's own audit records by id, or ``404`` if unknown/not theirs."""
    record = await session.get(EmergencyRequest, allocation_id)
    if record is None or record.dispatcher_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="allocation not found")
    return AllocationAuditRead.model_validate(record)


@router.get("", response_model=list[AllocationAuditRead])
async def list_allocations(
    session: SessionDep,
    actor: ReaderDep,
    status_filter: Annotated[Status | None, Query(alias="status")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> list[AllocationAuditRead]:
    """List the caller's own audit records, newest first; filter by ``status``/``from``/``to``."""
    query = (
        select(EmergencyRequest)
        .where(EmergencyRequest.dispatcher_id == actor.id)
        .order_by(EmergencyRequest.created_at.desc())
    )
    if status_filter is not None:
        query = query.where(EmergencyRequest.status == status_filter)
    if from_ is not None:
        query = query.where(EmergencyRequest.created_at >= from_)
    if to is not None:
        query = query.where(EmergencyRequest.created_at <= to)
    records = (await session.scalars(query)).all()
    return [AllocationAuditRead.model_validate(record) for record in records]
