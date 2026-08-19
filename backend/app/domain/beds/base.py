"""Bed Data Source Abstraction — the Bridge interface (docs/01-architecture.md §5).

The allocation engine reads and reserves bed availability through this single interface and
is unaware of *how* the data is sourced. Connecting a real EMR is "add an implementation +
change config" with no change to matching logic (thesis §3.11, NFR9) — this decoupling is
what makes the engine resilient to the LHIMS→GHIMS transition, and is proved (not merely
asserted) by shipping two independent implementations plus a third, test-only one that
needs zero changes under ``domain/allocation/`` (S7/NFR9; see
``tests/unit/test_bed_source_conformance.py``).

Five operations: ``name`` identifies the adapter in config/logs; ``fetch`` is the advisory
read used to build candidates; ``reserve``/``release`` are the only writes, both atomic
compare-and-set against the ``bed_state`` ``version`` column (docs/02 §3.2); ``health``
reports reachability. **Reads are advisory; the compare-and-set is authoritative** — a
stale ``fetch`` costs a wasted ``reserve`` attempt, never a double allocation (docs/01 §7).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.parameters import BedType


class BedUnavailableError(Exception):
    """Raised when an allocation is attempted against a facility/bed type with no free bed."""


class VersionConflict(Exception):
    """Raised by ``reserve`` when ``expect_version`` no longer matches the current row.

    Not necessarily a contended race — it is also raised when the target row does not
    exist at all (e.g. an unknown facility/bed_type pair), since the caller's response is
    identical either way: drop this candidate and try the next one (docs/01 §7).
    """


@dataclass(frozen=True)
class BedState:
    """A facility's availability for one bed type, as read from a source (docs/02 §3.2)."""

    facility_id: uuid.UUID
    bed_type: BedType
    total_beds: int
    available_beds: int
    version: int
    updated_at: datetime


@dataclass(frozen=True)
class HealthStatus:
    """Whether a source is currently reachable (docs/01 §5). ``detail`` is set only on failure."""

    healthy: bool
    detail: str | None = None


class BedDataSource(ABC):
    """Abstract source of live bed availability + reservation for a facility (docs/01 §5)."""

    @abstractmethod
    def name(self) -> str:
        """Identify this adapter in configuration and logs (e.g. ``"manual"``)."""
        raise NotImplementedError

    @abstractmethod
    async def fetch(self, facility_id: uuid.UUID) -> list[BedState]:
        """Return current bed state for every bed type this facility tracks."""
        raise NotImplementedError

    @abstractmethod
    async def reserve(self, facility_id: uuid.UUID, bed_type: BedType, expect_version: int) -> None:
        """Atomically decrement availability if the row is still at ``expect_version``.

        Raises ``VersionConflict`` on any mismatch (concurrent write, or no such row) —
        never partially applies, never returns a value to check; success is "did not raise".
        """
        raise NotImplementedError

    @abstractmethod
    async def release(self, facility_id: uuid.UUID, bed_type: BedType) -> None:
        """Return one bed to availability (capped at capacity). Best-effort, does not raise."""
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Report whether this source is currently reachable."""
        raise NotImplementedError
