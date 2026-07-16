"""``FacilityManagementSystemSource`` — Bridge stub (docs/01 §3.2, status: specified).

A configurable polling adapter for any facility REST endpoint: the URL, auth, and the
field mapping that translates the endpoint's response into a bed count are all supplied via
config. Specified at the interface level only — the prototype implements just
``SimulationDataSource`` (PRD §5). Calling ``get_available_beds`` raises ``NotImplementedError``
so a misconfiguration surfaces loudly instead of returning a wrong count.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from app.domain.beds.base import BedDataSource
from app.parameters import BedType


class FacilityManagementSystemSource(BedDataSource):
    """Polling adapter for a facility's own REST endpoint (specified, not built)."""

    def __init__(
        self,
        base_url: str,
        auth_token: str | None = None,
        field_mapping: Mapping[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._auth_token = auth_token
        # Maps response field names onto (facility, bed_type, available) — config-driven.
        self._field_mapping = dict(field_mapping or {})

    async def get_available_beds(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        raise NotImplementedError(
            "FacilityManagementSystemSource is specified, not implemented in the prototype "
            "(docs/01-architecture.md §3.2)."
        )
