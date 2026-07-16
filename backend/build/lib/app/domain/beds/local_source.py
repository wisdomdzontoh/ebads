"""``LocalBedCountSource`` — reads EBADS's own live ``bed_count`` table (docs/02 §2.2).

The default bed source for a live (non-simulation) allocation request: it reads the
availability that is maintained via ``PATCH /facilities/{id}/beds`` and seeded by the
facility loader. This is the connector between the documented ``bed_count`` store and the
live dispatch path (docs/04 §4, RB-3); the four Bridge adapters in docs/01 §3.2 cover
*external* bed data, whereas this reads the engine's own registry.

[IMPL] Not named in docs/01 §3.2's four-row table, but required for the live path to read a
documented table. Flagged for researcher review.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.domain.beds.base import BedDataSource
from app.parameters import BedType


class LocalBedCountSource(BedDataSource):
    """Live bed availability from the local ``bed_count`` registry (docs/02 §2.2)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_available_beds(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        """Return available beds from ``bed_count``; 0 if no row exists for that pair."""
        available = await self._session.scalar(
            select(BedCount.available).where(
                BedCount.facility_id == facility_id,
                BedCount.bed_type == bed_type,
            )
        )
        return int(available) if available is not None else 0
