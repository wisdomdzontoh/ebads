"""Bed Data Source Abstraction — the Bridge interface (docs/01-architecture.md §3.2).

The allocation engine reads bed availability through this single abstract interface and is
unaware of *how* the data is sourced. Moving from simulation to a live EMR is "add an
implementation + change config" with no change to matching logic (thesis §3.11) — this
decoupling is what makes the engine resilient to the LHIMS→GHIMS transition.

The interface is intentionally one method: ``get_available_beds``. Mutation of bed state
(decrement on allocation, release on discharge) is specific to ``SimulationDataSource`` and
is not part of the abstraction — a live source reflects reality from its backing system, it
is not written to by the engine.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.parameters import BedType


class BedUnavailableError(Exception):
    """Raised when an allocation is attempted against a facility/bed type with no free bed."""


class BedDataSource(ABC):
    """Abstract source of live bed availability for a facility (docs/01 §3.2)."""

    @abstractmethod
    async def get_available_beds(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        """Return the number of available beds of ``bed_type`` at ``facility_id`` (>= 0)."""
        raise NotImplementedError
