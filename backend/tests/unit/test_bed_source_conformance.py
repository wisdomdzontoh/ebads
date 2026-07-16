"""Bridge interface conformance (docs/12-testing.md §4).

Proves every concrete bed data source conforms to the ``BedDataSource`` interface, that the
abstract base cannot be instantiated, and that the three *specified* stubs fail loudly
(``NotImplementedError``) rather than returning a wrong bed count. No database needed.
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.beds import (
    BedDataSource,
    FacilityManagementSystemSource,
    HL7FHIRSource,
    NationalEMRSource,
    SimulationDataSource,
)
from app.parameters import BedType

ALL_SOURCES = [
    SimulationDataSource,
    FacilityManagementSystemSource,
    NationalEMRSource,
    HL7FHIRSource,
]

# The three sources specified-but-not-built in the prototype, with placeholder config.
SPECIFIED_STUBS = [
    FacilityManagementSystemSource(base_url="https://example.test"),
    NationalEMRSource(base_url="https://emr.example.test"),
    HL7FHIRSource(fhir_base_url="https://fhir.example.test/R4"),
]


@pytest.mark.parametrize("source_cls", ALL_SOURCES)
def test_source_conforms_to_interface(source_cls: type) -> None:
    """Every implementation is a BedDataSource and provides ``get_available_beds``."""
    assert issubclass(source_cls, BedDataSource)
    assert callable(source_cls.get_available_beds)


def test_abstract_base_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        BedDataSource()  # type: ignore[abstract]


@pytest.mark.parametrize("stub", SPECIFIED_STUBS)
async def test_specified_stub_raises_not_implemented(stub: BedDataSource) -> None:
    with pytest.raises(NotImplementedError):
        await stub.get_available_beds(uuid.uuid4(), BedType.ICU)
