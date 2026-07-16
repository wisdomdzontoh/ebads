"""``NationalEMRSource`` — Bridge stub (docs/01 §3.2, status: specified).

Adapter for Ghana's national EMR (LHIMS, and its GHIMS successor). The whole point of the
Bridge is that swapping to this source when the national platform stabilises requires no
change to matching logic (thesis §3.11). Specified at the interface level only;
``get_available_beds`` raises ``NotImplementedError`` in the prototype (PRD §5).
"""

from __future__ import annotations

import uuid

from app.domain.beds.base import BedDataSource
from app.parameters import BedType


class NationalEMRSource(BedDataSource):
    """Adapter for Ghana's national EMR — LHIMS / GHIMS (specified, not built)."""

    def __init__(self, base_url: str, auth_token: str | None = None) -> None:
        self._base_url = base_url
        self._auth_token = auth_token

    async def get_available_beds(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        raise NotImplementedError(
            "NationalEMRSource is specified, not implemented in the prototype "
            "(docs/01-architecture.md §3.2)."
        )
