"""Request/response schemas for ``/registrations`` (docs/02-data-model.md §2.4, FR16)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.parameters import BedType, DataSource, FacilityRequestStatus, Tier

_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LON_MIN, _LON_MAX = -180.0, 180.0


class FacilityRequestCreate(BaseModel):
    """Body of the public ``POST /registrations`` — carries no privilege (FR16)."""

    facility_name: str = Field(min_length=1)
    ghs_code: str = Field(min_length=1)
    tier: Tier
    contact_email: EmailStr
    contact_phone: str = Field(min_length=1)


class FacilityRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    facility_name: str
    ghs_code: str
    tier: Tier
    contact_email: str
    contact_phone: str
    status: FacilityRequestStatus
    reviewed_by: uuid.UUID | None
    rejection_reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class FacilityRequestApprove(BaseModel):
    """Body of ``POST /registrations/{id}/approve``.

    The system_administrator supplies the registry-grade attributes the request itself
    does not capture, plus credentials for the new facility's first administrator.
    """

    latitude: float = Field(ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(ge=_LON_MIN, le=_LON_MAX)
    supported_bed_types: list[BedType] = Field(min_length=1)
    # Null = manual maintenance (docs/02 §3.1) — the default for a newly approved facility.
    active_data_source: DataSource | None = None
    initial_admin_email: EmailStr
    initial_admin_password: str = Field(min_length=1)


class FacilityRequestReject(BaseModel):
    reason: str = Field(min_length=1)


class ApprovalResult(BaseModel):
    """Response of ``POST /registrations/{id}/approve``: the new facility and its admin."""

    facility_id: uuid.UUID
    facility_name: str
    admin_user_id: uuid.UUID
    admin_email: str
