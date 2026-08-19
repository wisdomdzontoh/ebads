"""Facility Registry Service — manages the static facility registry (docs/01 §3.1).

All persistence for facilities and their live bed counts goes through this service so the
API routes stay thin. Each method takes the request-scoped ``AsyncSession`` and returns ORM
objects (with ``bed_counts`` eagerly loaded via the relationship's ``selectin`` strategy);
``None`` signals "facility not found" so routes can map that to a 404.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.facility import BedCountUpdate, FacilityCreate, FacilityUpdate
from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility


class FacilityRegistryService:
    """CRUD operations for facilities and their bed counts (docs/04-api-spec.md §3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_facility(self, data: FacilityCreate) -> Facility:
        """Register a new facility (docs/04 §3 ``POST /facilities``).

        A new facility starts with no bed counts; they are set via ``update_beds``.
        """
        facility = Facility(
            name=data.name,
            # Numeric(9,6) columns hold Decimal; convert from the JSON float exactly via str.
            latitude=Decimal(str(data.latitude)),
            longitude=Decimal(str(data.longitude)),
            tier=data.tier,
            supported_bed_types=data.supported_bed_types,
            contact_phone=data.contact_phone,
            active_data_source=data.active_data_source,
        )
        self._session.add(facility)
        await self._session.commit()
        await self._session.refresh(facility)
        return facility

    async def get_facility(self, facility_id: uuid.UUID) -> Facility | None:
        """Return one facility by id, or ``None`` if it does not exist."""
        return await self._session.get(Facility, facility_id)

    async def list_facilities(self, updated_since: datetime | None = None) -> list[Facility]:
        """List facilities, optionally only those changed since ``updated_since``.

        The ``updated_since`` filter backs the mobile cache's incremental sync
        (docs/04 §3 ``?updated_since=``).
        """
        query = select(Facility).order_by(Facility.name)
        if updated_since is not None:
            query = query.where(Facility.updated_at >= updated_since)
        result = await self._session.scalars(query)
        return list(result.all())

    async def update_facility(
        self, facility_id: uuid.UUID, data: FacilityUpdate
    ) -> Facility | None:
        """Replace a facility's static attributes (docs/04 §3 ``PUT /facilities/{id}``)."""
        facility = await self._session.get(Facility, facility_id)
        if facility is None:
            return None
        facility.name = data.name
        facility.latitude = Decimal(str(data.latitude))
        facility.longitude = Decimal(str(data.longitude))
        facility.tier = data.tier
        facility.supported_bed_types = data.supported_bed_types
        facility.contact_phone = data.contact_phone
        facility.active_data_source = data.active_data_source
        await self._session.commit()
        await self._session.refresh(facility)
        return facility

    async def update_beds(
        self, facility_id: uuid.UUID, data: BedCountUpdate, updated_by: uuid.UUID | None = None
    ) -> Facility | None:
        """Upsert one bed-type count for a facility (docs/04 §3 ``PATCH .../beds``).

        Updates the existing row for ``(facility, bed_type)`` if present, else inserts one.
        The ``available <= capacity`` invariant is enforced by the schema and the DB.
        ``version`` is incremented on every write (docs/02 §3.2 invariant) — this is a human
        correction via the portal, so ``updated_by`` is recorded (unlike an adapter's
        ``reserve``/``release``, which leave it null).
        """
        facility = await self._session.get(Facility, facility_id)
        if facility is None:
            return None
        existing = next((bc for bc in facility.bed_counts if bc.bed_type == data.bed_type), None)
        if existing is None:
            facility.bed_counts.append(
                BedCount(
                    bed_type=data.bed_type,
                    available=data.available,
                    capacity=data.capacity,
                    updated_by=updated_by,
                )
            )
        else:
            existing.available = data.available
            existing.capacity = data.capacity
            existing.version += 1
            existing.updated_by = updated_by
        await self._session.commit()
        await self._session.refresh(facility)
        return facility
