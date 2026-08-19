"""Facility registration -> approval (docs/02 §2.4, FR16). Mounted under ``/api/v1``.

``POST /registrations`` is public — no dependency, no privilege conferred. Everything else
is system_administrator only, via ``require_permission("facility_request", ...)``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.registration import (
    ApprovalResult,
    FacilityRequestApprove,
    FacilityRequestCreate,
    FacilityRequestRead,
    FacilityRequestReject,
)
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.domain.registry.service import (
    ApproveInput,
    RegistryService,
    RequestAlreadyReviewedError,
    RequestNotFoundError,
    SubmitRequestInput,
)
from app.parameters import FacilityRequestStatus, PermissionAction
from app.security.dependencies import require_permission

router = APIRouter(prefix="/registrations", tags=["registrations"])


def _service(session: Annotated[AsyncSession, Depends(get_session)]) -> RegistryService:
    return RegistryService(session)


ServiceDep = Annotated[RegistryService, Depends(_service)]
ReviewerDep = Annotated[
    UserAccount, Depends(require_permission("facility_request", PermissionAction.APPROVE))
]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FacilityRequestRead)
async def submit_registration(
    payload: FacilityRequestCreate, service: ServiceDep
) -> FacilityRequestRead:
    """Submit a facility registration request — public, no account required (FR16)."""
    request = await service.submit_request(
        SubmitRequestInput(
            facility_name=payload.facility_name,
            ghs_code=payload.ghs_code,
            tier=payload.tier,
            contact_email=payload.contact_email,
            contact_phone=payload.contact_phone,
        )
    )
    return FacilityRequestRead.model_validate(request)


@router.get("", response_model=list[FacilityRequestRead])
async def list_registrations(
    service: ServiceDep,
    _reviewer: ReviewerDep,
    status_filter: Annotated[FacilityRequestStatus | None, Query(alias="status")] = None,
) -> list[FacilityRequestRead]:
    """List facility requests, newest first (system_administrator only)."""
    requests = await service.list_requests(status_filter)
    return [FacilityRequestRead.model_validate(r) for r in requests]


@router.post("/{request_id}/approve", response_model=ApprovalResult)
async def approve_registration(
    request_id: uuid.UUID,
    payload: FacilityRequestApprove,
    service: ServiceDep,
    reviewer: ReviewerDep,
) -> ApprovalResult:
    """Approve a pending request: creates the facility and its first admin (FR16)."""
    try:
        facility, admin = await service.approve(
            request_id,
            ApproveInput(
                latitude=payload.latitude,
                longitude=payload.longitude,
                supported_bed_types=payload.supported_bed_types,
                active_data_source=payload.active_data_source,
                initial_admin_email=payload.initial_admin_email,
                initial_admin_password=payload.initial_admin_password,
            ),
            reviewer,
        )
    except RequestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found") from exc
    except RequestAlreadyReviewedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "request already reviewed") from exc
    return ApprovalResult(
        facility_id=facility.id,
        facility_name=facility.name,
        admin_user_id=admin.id,
        admin_email=admin.email,
    )


@router.post("/{request_id}/reject", response_model=FacilityRequestRead)
async def reject_registration(
    request_id: uuid.UUID,
    payload: FacilityRequestReject,
    service: ServiceDep,
    reviewer: ReviewerDep,
) -> FacilityRequestRead:
    """Reject a pending request, recording why (system_administrator only)."""
    try:
        request = await service.reject(request_id, payload.reason, reviewer)
    except RequestNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "request not found") from exc
    except RequestAlreadyReviewedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "request already reviewed") from exc
    return FacilityRequestRead.model_validate(request)
