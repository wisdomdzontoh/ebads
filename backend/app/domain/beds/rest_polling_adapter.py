"""``RESTPollingAdapter`` — Bridge stub for configurable polling of any facility REST endpoint

(docs/01 §5, status: specified). The URL, auth, and the field mapping that translates the
endpoint's response into a bed count are all supplied via config. Specified at the interface
level only — every data-touching method raises ``NotImplementedError`` so a
misconfiguration surfaces loudly instead of returning a wrong count.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from app.domain.beds.base import BedDataSource, BedState, HealthStatus
from app.parameters import BedType

_NOT_BUILT = (
    "RESTPollingAdapter is specified, not implemented in the prototype "
    "(docs/01-architecture.md §5)."
)


class RESTPollingAdapter(BedDataSource):
    """Configurable polling adapter for a facility's own REST endpoint (specified, not built)."""

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

    def name(self) -> str:
        return "rest_polling"

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
