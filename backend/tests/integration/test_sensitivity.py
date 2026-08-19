"""End-to-end sensitivity analysis over a small grid (docs/08 §4, RB-8).

Runs the default + steeper-critical capability variants over a tiny 3-algorithm grid and
asserts the survival table has one classified row per hypothesis and one column per variant.
The substantive classification is data-dependent and not asserted — the test proves the
machinery runs and tabulates, not a particular scientific outcome (docs/08 header).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analysis.sensitivity import Variant, run_sensitivity
from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import AlgorithmName, BedType, Tier
from app.simulation.distance_matrix import build_distance_matrix, save_distance_matrix
from app.simulation.runner import GridConfig
from tests.integration.conftest import TEST_DATABASE_URL

_FACILITIES = [
    ("Korle Bu", 5.5366, -0.2261),
    ("37 Military", 5.5826, -0.1880),
    ("Ridge Hospital", 5.5641, -0.1969),
]
_ALL_BED_TYPES = [BedType.GENERAL, BedType.ICU, BedType.MATERNITY_SPECIALIST]
_TIERS = [Tier.TERTIARY, Tier.SECONDARY, Tier.PRIMARY]

_VARIANTS = [
    Variant("default", "baseline", None, None, None),
    Variant(
        "capability_steep_critical",
        "capability",
        None,
        None,
        {"critical": {"tertiary": 1.0, "secondary": 0.4, "primary": 0.1}},
    ),
]


@pytest_asyncio.fixture
async def sessionmaker() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed(db_session: AsyncSession) -> None:
    """Register a small multi-tier facility set (so capability actually varies)."""
    for (name, lat, lon), tier in zip(_FACILITIES, _TIERS, strict=True):
        facility = Facility(
            name=name,
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lon)),
            tier=tier,
            supported_bed_types=list(_ALL_BED_TYPES),
            contact_phone="+233000000000",
        )
        db_session.add(facility)
        await db_session.flush()
        for bed_type in _ALL_BED_TYPES:
            db_session.add(
                BedCount(facility_id=facility.id, bed_type=bed_type, available=12, capacity=12)
            )
    await db_session.commit()


async def test_sensitivity_produces_survival_table(
    db_session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    """run_sensitivity yields a hypothesis-survival table over the variants (docs/08 §4)."""
    await _seed(db_session)
    matrix_path = tmp_path / "distance_matrix.parquet"
    matrix = await build_distance_matrix(_FACILITIES, LiveTravelTimeService(""), grid_size=(5, 5))
    save_distance_matrix(matrix, matrix_path)

    config = GridConfig(
        study_id="sens-study",
        base_seed=20260617,
        algorithms=list(AlgorithmName),  # all three — hypotheses compare across them
        occupancies=[0.75, 1.00],  # include 100% so H3's FRR comparison has a scenario
        runs=4,
        events=3,
        distance_matrix=matrix_path,
        out_dir=tmp_path,
    )

    summary, details = await run_sensitivity(_VARIANTS, config, sessionmaker=sessionmaker)

    assert set(summary["hypothesis"]) == {"H1", "H2", "H3"}
    assert {"default", "capability_steep_critical", "classification"} <= set(summary.columns)
    assert set(summary["classification"]) <= {"robust", "conditional", "unsupported"}
    # Both variants appear in the long-form details.
    assert set(details["variant"]) == {"default", "capability_steep_critical"}
