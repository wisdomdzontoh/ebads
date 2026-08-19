"""Bridge interface conformance (docs/01-architecture.md §5, FR2, NFR9, S7).

Proves every concrete bed data source conforms to ``BedDataSource``, that the abstract base
cannot be instantiated, that the two *specified* stubs fail loudly (``NotImplementedError``)
rather than returning a wrong count, and — the load-bearing claim of NFR9/S7 — that a novel
third implementation, defined nowhere near ``domain/beds/`` or ``domain/allocation/``, works
with the allocation engine's candidate-building unchanged. No database needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db.models.facility import Facility
from app.domain.allocation.service import AllocationRequest, AllocationService
from app.domain.beds import (
    BedDataSource,
    BedState,
    FHIRAdapter,
    GHSDataAdapter,
    HealthStatus,
    ManualAdapter,
    RESTPollingAdapter,
    SimulationDataSource,
)
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.parameters import BedType, Tier

BUILT_SOURCES = [ManualAdapter, GHSDataAdapter, SimulationDataSource]
SPECIFIED_STUB_CLASSES = [FHIRAdapter, RESTPollingAdapter]

# The two sources specified-but-not-built in the prototype, with placeholder config.
SPECIFIED_STUBS: list[BedDataSource] = [
    FHIRAdapter(fhir_base_url="https://fhir.example.test/R4"),
    RESTPollingAdapter(base_url="https://example.test"),
]


@pytest.mark.parametrize("source_cls", BUILT_SOURCES + SPECIFIED_STUB_CLASSES)
def test_source_conforms_to_interface(source_cls: type) -> None:
    """Every implementation is a BedDataSource providing all five interface methods."""
    assert issubclass(source_cls, BedDataSource)
    for method in ("name", "fetch", "reserve", "release", "health"):
        assert callable(getattr(source_cls, method))


def test_abstract_base_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        BedDataSource()  # type: ignore[abstract]


def test_manual_and_ghs_adapters_have_distinct_names() -> None:
    """GHSDataAdapter subclasses ManualAdapter over the same store (see its module docstring)

    — distinct ``name()`` is what makes them independently registrable/identifiable.
    ``name()`` touches no session, so ``None`` stands in for one here.
    """
    assert ManualAdapter(session=None).name() == "manual"  # type: ignore[arg-type]
    assert GHSDataAdapter(session=None).name() == "ghs_data"  # type: ignore[arg-type]


@pytest.mark.parametrize("stub", SPECIFIED_STUBS)
async def test_specified_stub_raises_not_implemented(stub: BedDataSource) -> None:
    with pytest.raises(NotImplementedError):
        await stub.fetch(uuid.uuid4())
    with pytest.raises(NotImplementedError):
        await stub.reserve(uuid.uuid4(), BedType.ICU, expect_version=0)
    with pytest.raises(NotImplementedError):
        await stub.release(uuid.uuid4(), BedType.ICU)
    with pytest.raises(NotImplementedError):
        await stub.health()


class _StubTravel(TravelTimeService):
    """Fixed travel time, so the candidate-building test needs no live maps service."""

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=12.0, is_estimated=False)


class _ThirdPartyAdapter(BedDataSource):
    """A hypothetical third ``BedDataSource``, defined here in the test — not under

    ``domain/beds/`` or ``domain/allocation/``. That it works with
    ``AllocationService._build_candidates`` unchanged is the whole proof: the method takes
    ``bed_source: BedDataSource`` (the abstract type), so any conformer satisfies it by
    construction (NFR9/S7).
    """

    def name(self) -> str:
        return "third_party"

    async def fetch(self, facility_id: uuid.UUID) -> list[BedState]:
        return [
            BedState(
                facility_id=facility_id,
                bed_type=BedType.ICU,
                total_beds=5,
                available_beds=3,
                version=1,
                updated_at=datetime.now(UTC),
            )
        ]

    async def reserve(
        self, facility_id: uuid.UUID, bed_type: BedType, expect_version: int
    ) -> None:
        raise NotImplementedError("not exercised by this test")

    async def release(self, facility_id: uuid.UUID, bed_type: BedType) -> None:
        raise NotImplementedError("not exercised by this test")

    async def health(self) -> HealthStatus:
        return HealthStatus(healthy=True)


async def test_third_adapter_needs_no_allocation_code_changes() -> None:
    """NFR9/S7, structurally: a novel adapter feeds candidate-building with zero changes

    to ``domain/allocation/`` or ``domain/beds/`` — this test only ever imports the public
    ``BedDataSource`` ABC from those packages, never edits them.
    """
    facility = Facility(
        id=uuid.uuid4(),
        name="Third-Party Test Facility",
        latitude=Decimal("5.6"),
        longitude=Decimal("-0.2"),
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    # _build_candidates touches only self._travel and the passed bed_source — no DB session
    # is used, so a real one is unnecessary for this structural proof.
    service = AllocationService(session=None, travel_service=_StubTravel())  # type: ignore[arg-type]
    request = AllocationRequest(patient_lat=5.6, patient_lon=-0.2, required_bed_type=BedType.ICU)

    candidates = await service._build_candidates(request, [facility], _ThirdPartyAdapter())

    assert len(candidates) == 1
    assert candidates[0].available_beds == 3
    assert candidates[0].travel_time_min == 12.0
