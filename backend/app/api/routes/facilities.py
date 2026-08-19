"""Facility Registry endpoints (docs/04-api-spec.md §3).

Thin HTTP layer over ``FacilityRegistryService``: it validates input via Pydantic schemas,
delegates persistence to the service, and maps a missing facility to ``404``. Mounted under
``/api/v1`` by the app factory.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.facility import (
    BedCountUpdate,
    FacilityCreate,
    FacilityRead,
    FacilityUpdate,
)
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.domain.audit import service as audit
from app.domain.facilities.service import FacilityRegistryService
from app.parameters import PermissionAction
from app.security.dependencies import require_permission

router = APIRouter(prefix="/facilities", tags=["facilities"])


def _service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FacilityRegistryService:
    """Build a request-scoped Facility Registry Service over the DB session."""
    return FacilityRegistryService(session)


# Dependency alias so each route declares the service the modern (Annotated) way.
ServiceDep = Annotated[FacilityRegistryService, Depends(_service)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Any authenticated role may read the registry (FR21/PRD §2 — read is unrestricted).
ReaderDep = Annotated[UserAccount, Depends(require_permission("facility", PermissionAction.READ))]
# Direct creation bypasses the registration/approval flow (docs/registrations.py is the
# real onboarding path) — kept for internal/seed use, system_administrator only.
CreatorDep = Annotated[UserAccount, Depends(require_permission("facility", PermissionAction.WRITE))]
# own_facility, scoped by the {facility_id} path param.
ProfileWriterDep = Annotated[
    UserAccount,
    Depends(
        require_permission("facility", PermissionAction.WRITE, facility_id_param="facility_id")
    ),
]
BedWriterDep = Annotated[
    UserAccount,
    Depends(
        require_permission("bed_state", PermissionAction.WRITE, facility_id_param="facility_id")
    ),
]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FacilityRead)
async def register_facility(
    payload: FacilityCreate,
    service: ServiceDep,
    session: SessionDep,
    actor: CreatorDep,
) -> FacilityRead:
    """Register a facility directly (system_administrator; internal/seed use)."""
    facility = await service.create_facility(payload)
    await audit.record(
        session, actor.id, "create", "facility", facility.id, {"name": facility.name}
    )
    await session.commit()
    return FacilityRead.model_validate(facility)


@router.get("", response_model=list[FacilityRead])
async def list_facilities(
    service: ServiceDep,
    _reader: ReaderDep,
    updated_since: datetime | None = None,
) -> list[FacilityRead]:
    """List all facilities (mobile cache sync); ``?updated_since=`` filters by change time."""
    facilities = await service.list_facilities(updated_since=updated_since)
    return [FacilityRead.model_validate(f) for f in facilities]


@router.get("/{facility_id}", response_model=FacilityRead)
async def get_facility(
    facility_id: uuid.UUID,
    service: ServiceDep,
    _reader: ReaderDep,
) -> FacilityRead:
    """Fetch one facility by id, or ``404`` if unknown."""
    facility = await service.get_facility(facility_id)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    return FacilityRead.model_validate(facility)


@router.put("/{facility_id}", response_model=FacilityRead)
async def update_facility(
    facility_id: uuid.UUID,
    payload: FacilityUpdate,
    service: ServiceDep,
    session: SessionDep,
    actor: ProfileWriterDep,
) -> FacilityRead:
    """Replace a facility's static attributes (facility_administrator, own facility)."""
    facility = await service.update_facility(facility_id, payload)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    await audit.record(session, actor.id, "update", "facility", facility_id)
    await session.commit()
    return FacilityRead.model_validate(facility)


@router.patch("/{facility_id}/beds", response_model=FacilityRead)
async def update_facility_beds(
    facility_id: uuid.UUID,
    payload: BedCountUpdate,
    service: ServiceDep,
    session: SessionDep,
    actor: BedWriterDep,
) -> FacilityRead:
    """Upsert one bed-type count for a facility (facility_administrator/staff, own facility)."""
    facility = await service.update_beds(facility_id, payload, updated_by=actor.id)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    await audit.record(
        session, actor.id, "update", "bed_state", facility_id,
        {"bed_type": payload.bed_type.value, "available": payload.available},
    )
    await session.commit()
    return FacilityRead.model_validate(facility)
