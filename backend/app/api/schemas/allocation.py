"""Request/response schemas for the Allocation Service (docs/04-api-spec.md §4, docs/01 §7).

The response is a discriminated union on ``status``: a ``confirmed`` shape with the reserved
facility and ETA, or an ``escalated`` shape with the two fallbacks and
``requires_manual_decision``. Keeping them as distinct models makes ``/docs`` show exactly
the two documented payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.parameters import AlgorithmName, AllocationStatus, BedType, Tier, Urgency, WeightVector

_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LON_MIN, _LON_MAX = -180.0, 180.0


class AllocationCreate(BaseModel):
    """Body of ``POST /api/v1/allocations`` (docs/04 §4)."""

    patient_lat: float = Field(ge=_LAT_MIN, le=_LAT_MAX)
    patient_lon: float = Field(ge=_LON_MIN, le=_LON_MAX)
    urgency: Urgency | None = None
    required_bed_type: BedType
    simulation_session_id: uuid.UUID | None = None


class RecommendedFacility(BaseModel):
    """The reserved facility in a confirmed response (docs/04 §4)."""

    id: uuid.UUID
    name: str
    tier: Tier
    available_beds: int
    travel_time_minutes: float
    is_estimated_travel_time: bool
    latitude: float
    longitude: float
    contact_phone: str


class FacilityBrief(BaseModel):
    """A minimal facility reference used in an escalation fallback (docs/04 §4)."""

    id: uuid.UUID
    name: str
    travel_time_minutes: float
    available_beds: int


class AllocatedResponse(BaseModel):
    """Confirmed-reservation payload (docs/01 §7, FR8, FR19)."""

    id: uuid.UUID
    status: Literal[AllocationStatus.CONFIRMED] = AllocationStatus.CONFIRMED
    recommended_facility: RecommendedFacility
    algorithm_used: AlgorithmName
    weight_vector: WeightVector | None
    capability_match: float
    candidates_evaluated: int
    attempts: int
    eta_minutes: float
    selection_reason: str


class EscalatedResponse(BaseModel):
    """Escalation payload (docs/04 §4, FR11) — either no admissible candidate, or every

    candidate was claimed by a concurrent request before this one could reserve one.
    """

    id: uuid.UUID
    status: Literal[AllocationStatus.ESCALATED] = AllocationStatus.ESCALATED
    recommended_facility: None = None
    requires_manual_decision: Literal[True] = True
    nearest_within_radius: FacilityBrief | None
    nearest_available_outside_radius: FacilityBrief | None
    algorithm_used: AlgorithmName
    candidates_evaluated: int
    selection_reason: str


# Discriminated on ``status`` so clients/OpenAPI see the two distinct shapes.
AllocationResponse = Annotated[AllocatedResponse | EscalatedResponse, Field(discriminator="status")]


class AllocationAuditRead(BaseModel):
    """One persisted allocation decision, with its request's facts (docs/02 §3.4-3.5).

    Assembled from a joined ``Allocation`` (whose ``request`` relationship is eager-loaded)
    rather than ``model_validate``-ed directly — the two source tables are split, but the
    read model presents them as one record, matching the previous single-table shape.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    patient_lat: float
    patient_lon: float
    urgency: Urgency | None
    required_bed_type: BedType
    simulation_session_id: uuid.UUID | None
    algorithm_used: AlgorithmName
    weight_vector: dict[str, Any] | None
    selection_reason: str
    facility_id: uuid.UUID | None
    travel_time_minutes: float | None
    is_estimated_travel_time: bool
    eta_minutes: float | None
    capability_match: float | None
    candidates_evaluated: int
    attempts: int
    status: AllocationStatus


class ReservationRead(BaseModel):
    """The reservation behind a confirmed allocation (docs/02 §3.6)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    allocation_id: uuid.UUID
    expires_at: datetime
    acknowledged_at: datetime | None
    confirmed: bool
    released_at: datetime | None


class RefuseRequest(BaseModel):
    reason: str = Field(min_length=1)
