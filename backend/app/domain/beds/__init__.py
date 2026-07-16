"""Bed Data Source Abstraction (Bridge) — docs/01-architecture.md §3.2.

Exposes the abstract ``BedDataSource`` and its four concrete implementations: the built
``SimulationDataSource`` and the three specified stubs.
"""

from app.domain.beds.base import BedDataSource, BedUnavailableError
from app.domain.beds.facility_management_source import FacilityManagementSystemSource
from app.domain.beds.hl7_fhir_source import HL7FHIRSource
from app.domain.beds.local_source import LocalBedCountSource
from app.domain.beds.national_emr_source import NationalEMRSource
from app.domain.beds.simulation_source import SimulationDataSource

__all__ = [
    "BedDataSource",
    "BedUnavailableError",
    "FacilityManagementSystemSource",
    "HL7FHIRSource",
    "LocalBedCountSource",
    "NationalEMRSource",
    "SimulationDataSource",
]
