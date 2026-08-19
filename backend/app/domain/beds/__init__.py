"""Bed Data Source Abstraction (Bridge) — docs/01-architecture.md §5.

Exposes the abstract ``BedDataSource`` and its four concrete implementations: the built
``ManualAdapter`` and ``GHSDataAdapter``, the two specified stubs ``FHIRAdapter`` and
``RESTPollingAdapter``, plus ``SimulationDataSource`` (the prototype's simulation-only
source, not one of docs/01 §5's four adapters — see its module docstring).
"""

from app.domain.beds.base import (
    BedDataSource,
    BedState,
    BedUnavailableError,
    HealthStatus,
    VersionConflict,
)
from app.domain.beds.fhir_adapter import FHIRAdapter
from app.domain.beds.ghs_data_adapter import GHSDataAdapter
from app.domain.beds.manual_adapter import ManualAdapter
from app.domain.beds.rest_polling_adapter import RESTPollingAdapter
from app.domain.beds.simulation_source import SimulationDataSource

__all__ = [
    "BedDataSource",
    "BedState",
    "BedUnavailableError",
    "FHIRAdapter",
    "GHSDataAdapter",
    "HealthStatus",
    "ManualAdapter",
    "RESTPollingAdapter",
    "SimulationDataSource",
    "VersionConflict",
]
