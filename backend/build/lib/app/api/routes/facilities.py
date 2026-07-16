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
from app.db.session import get_session
from app.domain.facilities.service import FacilityRegistryService

router = APIRouter(prefix="/facilities", tags=["facilities"])


def _service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FacilityRegistryService:
    """Build a request-scoped Facility Registry Service over the DB session."""
    return FacilityRegistryService(session)


# Dependency alias so each route declares the service the modern (Annotated) way.
ServiceDep = Annotated[FacilityRegistryService, Depends(_service)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FacilityRead)
async def register_facility(
    payload: FacilityCreate,
    service: ServiceDep,
) -> FacilityRead:
    """Register a facility and return it with a generated id (docs/04 §3)."""
    facility = await service.create_facility(payload)
    return FacilityRead.model_validate(facility)


@router.get("", response_model=list[FacilityRead])
async def list_facilities(
    service: ServiceDep,
    updated_since: datetime | None = None,
) -> list[FacilityRead]:
    """List all facilities (mobile cache sync); ``?updated_since=`` filters by change time."""
    facilities = await service.list_facilities(updated_since=updated_since)
    return [FacilityRead.model_validate(f) for f in facilities]


@router.get("/{facility_id}", response_model=FacilityRead)
async def get_facility(
    facility_id: uuid.UUID,
    service: ServiceDep,
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
) -> FacilityRead:
    """Replace a facility's static attributes, or ``404`` if unknown."""
    facility = await service.update_facility(facility_id, payload)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    return FacilityRead.model_validate(facility)


@router.patch("/{facility_id}/beds", response_model=FacilityRead)
async def update_facility_beds(
    facility_id: uuid.UUID,
    payload: BedCountUpdate,
    service: ServiceDep,
) -> FacilityRead:
    """Upsert one bed-type count for a facility (non-simulation), or ``404`` if unknown."""
    facility = await service.update_beds(facility_id, payload)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="facility not found")
    return FacilityRead.model_validate(facility)
