"""``FHIRAdapter`` — Bridge stub for any HL7 FHIR R4 EMR (docs/01 §5, status: specified).

Connects via the ``Location``/``Bed`` resources. Specified at the interface level only —
every data-touching method raises ``NotImplementedError`` so a misconfiguration surfaces
loudly instead of returning a wrong count (PRD §4 non-goals: "connecting a real EMR is a
deployment activity requiring institutional access").
"""

from __future__ import annotations

import uuid

from app.domain.beds.base import BedDataSource, BedState, HealthStatus
from app.parameters import BedType

_NOT_BUILT = (
    "FHIRAdapter is specified, not implemented in the prototype (docs/01-architecture.md §5)."
)


class FHIRAdapter(BedDataSource):
    """Adapter for any HL7 FHIR R4 EMR (specified, not built)."""

    def __init__(self, fhir_base_url: str, auth_token: str | None = None) -> None:
        self._fhir_base_url = fhir_base_url
        self._auth_token = auth_token

    def name(self) -> str:
        return "fhir_r4"

    async def fetch(self, facility_id: uuid.UUID) -> list[BedState]:
        raise NotImplementedError(_NOT_BUILT)

    async def reserve(
        self, facility_id: uuid.UUID, bed_type: BedType, expect_version: int
    ) -> None:
        raise NotImplementedError(_NOT_BUILT)

    async def release(self, facility_id: uuid.UUID, bed_type: BedType) -> None:
        raise NotImplementedError(_NOT_BUILT)

    async def health(self) -> HealthStatus:
        raise NotImplementedError(_NOT_BUILT)
