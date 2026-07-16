"""Request/response schemas for the Facility Registry Service (docs/04-api-spec.md §3).

Pydantic v2 models are the typed contract for the ``/facilities`` endpoints. Field names
and shapes mirror the API spec and the data model (docs/02 §2.1-2.2); validation here keeps
malformed payloads from ever reaching the service or the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.parameters import BedType, DataSource, Tier

# Latitude/longitude bounds for basic sanity checking. The engine is GA-calibrated but the
# registry API does not reject out-of-region coordinates — only physically invalid ones.
_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LON_MIN, _LON_MAX = -180.0, 180.0


class FacilityBase(BaseModel):
    """Static facility attributes shared by create and update (docs/02 §2.1)."""

    name: str = Field(min_length=1)
    latitude: float = Field(ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(ge=_LON_MIN, le=_LON_MAX)
    tier: Tier
    supported_bed_types: list[BedType] = Field(min_length=1)
    contact_phone: str = Field(min_length=1)
    active_data_source: DataSource = DataSource.SIMULATION

    @field_validator("supported_bed_types")
    @classmethod
    def _no_duplicate_bed_types(cls, value: list[BedType]) -> list[BedType]:
        """A facility lists each supported bed type at most once."""
        if len(set(value)) != len(value):
            raise ValueError("supported_bed_types must not contain duplicates")
        return value


class FacilityCreate(FacilityBase):
    """Body of ``POST /api/v1/facilities`` (docs/04 §3)."""


class FacilityUpdate(FacilityBase):
    """Body of ``PUT /api/v1/facilities/{id}`` — full replacement of static attributes."""


class BedCountUpdate(BaseModel):
    """Body of ``PATCH /api/v1/facilities/{id}/beds`` (docs/04 §3).

    Enforces the docs/02 §4 invariants up front: ``available`` is non-negative and never
    exceeds ``capacity``.
    """

    bed_type: BedType
    available: int = Field(ge=0)
    capacity: int = Field(ge=0)

    @model_validator(mode="after")
    def _available_within_capacity(self) -> BedCountUpdate:
        if self.available > self.capacity:
            raise ValueError("available must not exceed capacity")
        return self


class BedCountRead(BaseModel):
    """A single bed-type availability row in a facility response (docs/02 §2.2)."""

    model_config = ConfigDict(from_attributes=True)

    bed_type: BedType
    available: int
    capacity: int
    updated_at: datetime


class FacilityRead(FacilityBase):
    """Facility representation returned by the API, including its live bed counts.

    Bed counts are embedded so a single ``GET /facilities`` gives the mobile cache (and
    RB-2) tier, supported bed types, capacity, and phone in one response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    bed_counts: list[BedCountRead] = []
