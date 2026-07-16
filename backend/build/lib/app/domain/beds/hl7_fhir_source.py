"""``HL7FHIRSource`` — Bridge stub (docs/01 §3.2, status: specified).

Connects to any HL7 FHIR R4 EMR (e.g. via the ``Location``/``Bed`` resources). Specified at
the interface level only; ``get_available_beds`` raises ``NotImplementedError`` in the
prototype (PRD §5).
"""

from __future__ import annotations

import uuid

from app.domain.beds.base import BedDataSource
from app.parameters import BedType


class HL7FHIRSource(BedDataSource):
    """Adapter for any HL7 FHIR R4 EMR (specified, not built)."""

    def __init__(self, fhir_base_url: str, auth_token: str | None = None) -> None:
        self._fhir_base_url = fhir_base_url
        self._auth_token = auth_token

    async def get_available_beds(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        raise NotImplementedError(
            "HL7FHIRSource is specified, not implemented in the prototype "
            "(docs/01-architecture.md §3.2)."
        )
