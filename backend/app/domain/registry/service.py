"""Facility registration -> approval (docs/02-data-model.md §2.4, FR16).

A ``facility_request`` carries no privilege. Approval is the only path that creates a
``facility`` — and, in the same transaction, its first ``facility_administrator`` account
(docs/01 §4: "no self-service path grants privilege; registration creates a request; only
approval creates an account"). The request itself does not capture the registry-grade
attributes (coordinates, supported bed types) — those are supplied by the approving
system_administrator, who is expected to have verified them, not merely echoing whatever
the requester claimed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.facility import Facility
from app.db.models.facility_request import FacilityRequest
from app.db.models.role import Role as RoleRow
from app.db.models.user_account import UserAccount
from app.domain.audit import service as audit
from app.parameters import BedType, DataSource, FacilityRequestStatus, Role, Tier
from app.security.passwords import hash_password


class RequestNotFoundError(Exception):
    """Raised when a ``facility_request`` id does not exist."""


class RequestAlreadyReviewedError(Exception):
    """Raised when approving/rejecting a request that is no longer pending."""


@dataclass(frozen=True)
class SubmitRequestInput:
    facility_name: str
    ghs_code: str
    tier: Tier
    contact_email: str
    contact_phone: str


@dataclass(frozen=True)
class ApproveInput:
    """Registry-grade attributes plus the new facility_administrator's credentials."""

    latitude: float
    longitude: float
    supported_bed_types: list[BedType]
    active_data_source: DataSource | None
    initial_admin_email: str
    initial_admin_password: str


class RegistryService:
    """Submission, listing, approval and rejection of facility requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def submit_request(self, data: SubmitRequestInput) -> FacilityRequest:
        """Create a pending request (public endpoint — confers no privilege, FR16)."""
        request = FacilityRequest(
            facility_name=data.facility_name,
            ghs_code=data.ghs_code,
            tier=data.tier,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
        )
        self._session.add(request)
        await self._session.commit()
        await self._session.refresh(request)
        return request

    async def list_requests(
        self, status_filter: FacilityRequestStatus | None = None
    ) -> list[FacilityRequest]:
        query = select(FacilityRequest).order_by(FacilityRequest.created_at.desc())
        if status_filter is not None:
            query = query.where(FacilityRequest.status == status_filter)
        return list((await self._session.scalars(query)).all())

    async def approve(
        self, request_id: uuid.UUID, data: ApproveInput, reviewed_by: UserAccount
    ) -> tuple[Facility, UserAccount]:
        """Approve a pending request: create the facility and its first admin, atomically."""
        request = await self._session.get(FacilityRequest, request_id)
        if request is None:
            raise RequestNotFoundError(str(request_id))
        if request.status != FacilityRequestStatus.PENDING:
            raise RequestAlreadyReviewedError(str(request_id))

        facility = Facility(
            name=request.facility_name,
            latitude=Decimal(str(data.latitude)),
            longitude=Decimal(str(data.longitude)),
            tier=request.tier,
            supported_bed_types=data.supported_bed_types,
            contact_phone=request.contact_phone,
            active_data_source=data.active_data_source,
        )
        self._session.add(facility)
        await self._session.flush()  # assigns facility.id

        admin_role = await self._session.scalar(
            select(RoleRow).where(RoleRow.name == Role.FACILITY_ADMINISTRATOR)
        )
        assert admin_role is not None  # seeded by migration 0005
        admin = UserAccount(
            email=data.initial_admin_email,
            password_hash=hash_password(data.initial_admin_password),
            role_id=admin_role.id,
            facility_id=facility.id,
            created_by=reviewed_by.id,
        )
        self._session.add(admin)

        request.status = FacilityRequestStatus.APPROVED
        request.reviewed_by = reviewed_by.id
        request.reviewed_at = datetime.now(UTC)

        await self._session.flush()  # assigns admin.id
        await audit.record(
            self._session, reviewed_by.id, "approve", "facility_request", request.id
        )
        await audit.record(
            self._session, reviewed_by.id, "create", "facility", facility.id,
            {"name": facility.name, "from_request": str(request.id)},
        )
        await audit.record(
            self._session, reviewed_by.id, "create", "user_account", admin.id,
            {"email": admin.email, "role": Role.FACILITY_ADMINISTRATOR.value},
        )

        await self._session.commit()
        await self._session.refresh(facility)
        await self._session.refresh(admin)
        return facility, admin

    async def reject(
        self, request_id: uuid.UUID, reason: str, reviewed_by: UserAccount
    ) -> FacilityRequest:
        request = await self._session.get(FacilityRequest, request_id)
        if request is None:
            raise RequestNotFoundError(str(request_id))
        if request.status != FacilityRequestStatus.PENDING:
            raise RequestAlreadyReviewedError(str(request_id))

        request.status = FacilityRequestStatus.REJECTED
        request.reviewed_by = reviewed_by.id
        request.rejection_reason = reason
        request.reviewed_at = datetime.now(UTC)

        await audit.record(
            self._session, reviewed_by.id, "reject", "facility_request", request.id,
            {"reason": reason},
        )
        await self._session.commit()
        await self._session.refresh(request)
        return request
