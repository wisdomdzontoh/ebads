"""Batch grid runner (docs/07-simulation.md §7, RB-6).

Runs a small grid end-to-end against the test database and asserts the shape of the per-run
metrics dataset and — the core guarantee — that re-running the identical grid reproduces
identical per-run metrics (deterministic seeds + fixed matrix ⇒ identical results).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import AlgorithmName, BedType, Tier
from app.simulation.distance_matrix import (
    build_distance_matrix,
    content_hash,
    save_distance_matrix,
)
from app.simulation.runner import (
    GridConfig,
    build_run_manifest,
    grid_config_from_manifest,
    run_grid,
)
from tests.integration.conftest import TEST_DATABASE_URL

_FACILITIES = [
    ("Korle Bu", 5.5366, -0.2261),
    ("37 Military", 5.5826, -0.1880),
    ("Tema General", 5.6698, -0.0166),
]
_ALL_BED_TYPES = [BedType.GENERAL, BedType.ICU, BedType.MATERNITY_SPECIALIST]


@pytest_asyncio.fixture
async def sessionmaker() -> async_sessionmaker[AsyncSession]:
    """An async session factory bound to the (already-migrated) test database."""
    engine = create_async_engine(TEST_DATABASE_URL)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed_facilities(db_session: AsyncSession) -> None:
    """Register the fixed facility set with full bed capacity for the grid to occupancy-seed."""
    for name, lat, lon in _FACILITIES:
        facility = Facility(
            name=name,
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lon)),
            tier=Tier.TERTIARY,
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


async def _build_matrix_file(path: Path) -> None:
    """Build a small Haversine distance matrix over the fixed facilities and save it."""
    matrix = await build_distance_matrix(
        _FACILITIES, LiveTravelTimeService(""), seed=0, grid_size=(6, 6)
    )
    save_distance_matrix(matrix, path)


async def test_grid_writes_per_run_metrics_and_is_reproducible(
    db_session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    """A 2-algorithm x 1-occupancy x 2-run grid yields 4 rows and reproduces identically."""
    await _seed_facilities(db_session)
    matrix_path = tmp_path / "distance_matrix.parquet"
    await _build_matrix_file(matrix_path)

    config = GridConfig(
        study_id="test-grid",
        base_seed=20260617,
        algorithms=[AlgorithmName.GREEDY, AlgorithmName.WEIGHTED],
        occupancies=[0.75],
        runs=2,
        events=3,
        distance_matrix=matrix_path,
        out_dir=tmp_path,
    )

    per_run, per_event = await run_grid(config, sessionmaker=sessionmaker)

    # 2 algorithms x 1 occupancy x 2 runs = 4 per-run rows.
    assert len(per_run) == 4
    assert set(per_run["algorithm"]) == {"greedy", "weighted"}
    assert {"atbp", "frr", "mcee", "cm", "cm_critical", "seed", "distance_matrix_sha256"} <= set(
        per_run.columns
    )
    assert len(per_event) > 0
    assert set(per_event["algorithm"]) == {"greedy", "weighted"}

    # Reproducibility: the identical grid produces identical per-run metrics (docs/07 §9).
    per_run_again, _ = await run_grid(config, sessionmaker=sessionmaker)
    key = ["algorithm", "occupancy", "run_index"]
    metric_columns = [*key, "atbp", "frr", "mcee", "cm", "cm_critical", "seed"]
    left = per_run[metric_columns].sort_values(key).reset_index(drop=True)
    right = per_run_again[metric_columns].sort_values(key).reset_index(drop=True)
    assert left.equals(right)


async def test_reproduces_grid_from_manifest(
    db_session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    """A grid reconstructed from its run manifest reproduces identical metrics (RB-10)."""
    await _seed_facilities(db_session)
    matrix_path = tmp_path / "distance_matrix.parquet"
    await _build_matrix_file(matrix_path)

    config = GridConfig(
        study_id="manifest-study",
        base_seed=20260617,
        algorithms=[AlgorithmName.WEIGHTED, AlgorithmName.URGENCY_ADAPTIVE],
        occupancies=[0.90],
        runs=2,
        events=3,
        distance_matrix=matrix_path,
        out_dir=tmp_path,
    )
    per_run, _ = await run_grid(config, sessionmaker=sessionmaker)

    # Persist the manifest, then rebuild the config purely from it (like CLI --from-manifest).
    manifest_path = tmp_path / "run_manifest.json"
    manifest = build_run_manifest(config, content_hash(matrix_path))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    reconstructed = grid_config_from_manifest(manifest_path, out_dir=tmp_path)
    assert reconstructed == config

    per_run_from_manifest, _ = await run_grid(reconstructed, sessionmaker=sessionmaker)
    key = ["algorithm", "occupancy", "run_index"]
    metric_columns = [*key, "atbp", "frr", "mcee", "cm", "cm_critical", "seed"]
    original = per_run[metric_columns].sort_values(key).reset_index(drop=True)
    reproduced = per_run_from_manifest[metric_columns].sort_values(key).reset_index(drop=True)
    assert original.equals(reproduced)
