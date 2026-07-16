"""Batch grid runner for the evaluation study (docs/07-simulation.md §7, RB-6).

Runs the full factorial grid — every algorithm x every occupancy scenario x ``runs`` repeats
— each as an isolated ``SimulationSession``, and writes two datasets under
``artifacts/sim/<study_id>/``: ``per_run_metrics.parquet`` (one row per run, the unit of
statistical analysis) and ``per_event_records.parquet`` (every processed event).

Seeds are derived so that, at a given (occupancy, run index), **all algorithms share the same
seed** and therefore the same generated event stream. docs/07 §7's pseudocode writes
``hash(algorithm, occupancy, run)``, but its very next sentence requires the same seed across
algorithm configurations to enable *paired* statistical tests (docs/08). Those conflict; this
runner honours the binding pairing requirement and makes the seed independent of the
algorithm. Every run still records the exact seed it used.

CLI (RB-6)::

    python -m app.simulation.runner --study-id 2026-06-17 --seed 20260617 \
      --algorithms greedy weighted urgency_adaptive \
      --occupancies 0.75 0.90 1.00 --runs 30 --events 100 \
      --distance-matrix artifacts/distance_matrix.parquet
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.simulation_allocation_event import SimulationAllocationEvent
from app.db.session import get_engine, get_sessionmaker
from app.domain.allocation.study_parameters import StudyParameters
from app.parameters import (
    EVENTS_PER_RUN,
    OCCUPANCY_SCENARIOS,
    RANDOM_SEED,
    RUNS_PER_CONFIGURATION,
    AlgorithmName,
)
from app.simulation.distance_matrix import (
    MatrixTravelTimeService,
    content_hash,
    load_distance_matrix,
)
from app.simulation.metrics import RunMetrics
from app.simulation.service import SessionConfig, SimulationService

# Filename of the manifest written next to a grid's outputs (consumed by RB-10 and the report).
RUN_MANIFEST_NAME = "run_manifest.json"

# Per-occupancy seed band. Runs at different occupancy indices never share a seed, while runs
# at the same (occupancy, run index) do — regardless of algorithm — which is what pairs them.
_SEED_OCCUPANCY_STRIDE = 1_000_000


def derive_seed(base_seed: int, occupancy_index: int, run_index: int) -> int:
    """Deterministic, algorithm-independent seed for a grid cell (docs/07 §7 pairing)."""
    return base_seed + occupancy_index * _SEED_OCCUPANCY_STRIDE + run_index


@dataclass(frozen=True)
class GridConfig:
    """The grid to sweep (algorithms x occupancies x runs) and where to read/write."""

    study_id: str
    base_seed: int
    algorithms: list[AlgorithmName]
    occupancies: list[float]
    runs: int
    events: int
    distance_matrix: Path
    out_dir: Path


def _run_metric_row(
    algorithm: AlgorithmName,
    occupancy: float,
    run_index: int,
    seed: int,
    session_id: str,
    matrix_hash: str,
    metrics: RunMetrics,
) -> dict[str, object]:
    """One per-run metrics record for ``per_run_metrics.parquet`` (docs/07 §8)."""
    return {
        "algorithm": algorithm.value,
        "occupancy": occupancy,
        "run_index": run_index,
        "seed": seed,
        "session_id": session_id,
        "distance_matrix_sha256": matrix_hash,
        "atbp": metrics.atbp,
        "frr": metrics.frr,
        "mcee": metrics.mcee,
        "cm": metrics.cm,
        "cm_critical": metrics.cm_critical,
        "events_total": metrics.events_total,
        "events_allocated": metrics.events_allocated,
        "events_escalated": metrics.events_escalated,
    }


def _event_row(
    algorithm: AlgorithmName,
    occupancy: float,
    run_index: int,
    record: SimulationAllocationEvent,
) -> dict[str, object]:
    """One per-event record for ``per_event_records.parquet`` (docs/07 §9)."""

    def _as_float(value: Decimal | None) -> float | None:
        return float(value) if value is not None else None

    return {
        "algorithm": algorithm.value,
        "occupancy": occupancy,
        "run_index": run_index,
        "session_id": str(record.session_id),
        "event_index": record.event_index,
        "virtual_arrival_min": float(record.virtual_arrival_min),
        "urgency": record.urgency.value,
        "required_bed_type": record.required_bed_type.value,
        "patient_lat": float(record.patient_lat),
        "patient_lon": float(record.patient_lon),
        "recommended_facility_id": (
            str(record.recommended_facility_id) if record.recommended_facility_id else None
        ),
        "travel_time_minutes": _as_float(record.travel_time_minutes),
        "time_to_bed_placement_min": _as_float(record.time_to_bed_placement_min),
        "capability_match": _as_float(record.capability_match),
        "candidates_evaluated": record.candidates_evaluated,
        "status": record.status.value,
        "los_minutes": _as_float(record.los_minutes),
        "bed_release_virtual_min": _as_float(record.bed_release_virtual_min),
    }


async def run_grid(
    config: GridConfig,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    study_parameters: StudyParameters | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute the whole grid and return (per-run metrics, per-event records) frames.

    ``sessionmaker`` defaults to the process factory (the configured database); tests inject
    a factory bound to the ephemeral test database. ``study_parameters`` defaults to the
    ``parameters.py`` configuration; the sensitivity driver passes a variant's bundle.
    """
    matrix = load_distance_matrix(config.distance_matrix)
    travel = MatrixTravelTimeService(matrix)
    sessionmaker = sessionmaker or get_sessionmaker()

    run_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for algorithm in config.algorithms:
        for occupancy_index, occupancy in enumerate(config.occupancies):
            for run_index in range(config.runs):
                seed = derive_seed(config.base_seed, occupancy_index, run_index)
                async with sessionmaker() as db:
                    service = SimulationService(db, travel, study_parameters)
                    sim = await service.create_session(
                        SessionConfig(
                            algorithm_config=algorithm,
                            occupancy_scenario=occupancy,
                            events_planned=config.events,
                            random_seed=seed,
                        )
                    )
                    metrics = await service.run_session(sim.id)
                    records = await service.get_events(sim.id)
                run_rows.append(
                    _run_metric_row(
                        algorithm, occupancy, run_index, seed, str(sim.id),
                        matrix.content_hash, metrics,
                    )
                )
                event_rows.extend(
                    _event_row(algorithm, occupancy, run_index, record) for record in records
                )
            print(f"  {algorithm.value} @ occ={occupancy}: {config.runs} runs done")
    return pd.DataFrame(run_rows), pd.DataFrame(event_rows)


def build_run_manifest(config: GridConfig, matrix_sha256: str) -> dict[str, object]:
    """Capture the grid config + matrix identity so the grid can be reproduced (docs/07 §9)."""
    return {
        "study_id": config.study_id,
        "grid": {
            "base_seed": config.base_seed,
            "algorithms": [algorithm.value for algorithm in config.algorithms],
            "occupancies": config.occupancies,
            "runs": config.runs,
            "events": config.events,
            "distance_matrix": str(config.distance_matrix),
            "distance_matrix_sha256": matrix_sha256,
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }


def grid_config_from_manifest(manifest_path: Path, out_dir: Path) -> GridConfig:
    """Reconstruct a :class:`GridConfig` from a run manifest, for reproduction (RB-10)."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    grid = data["grid"]
    return GridConfig(
        study_id=data["study_id"],
        base_seed=grid["base_seed"],
        algorithms=[AlgorithmName(name) for name in grid["algorithms"]],
        occupancies=list(grid["occupancies"]),
        runs=grid["runs"],
        events=grid["events"],
        distance_matrix=Path(grid["distance_matrix"]),
        out_dir=out_dir,
    )


async def _main(config: GridConfig) -> None:
    """RB-6 body: run the grid, write both Parquet datasets + the manifest, report totals."""
    per_run, per_event = await run_grid(config)
    study_dir = config.out_dir / config.study_id
    study_dir.mkdir(parents=True, exist_ok=True)
    per_run_path = study_dir / "per_run_metrics.parquet"
    per_event_path = study_dir / "per_event_records.parquet"
    manifest_path = study_dir / RUN_MANIFEST_NAME
    per_run.to_parquet(per_run_path, index=False)
    per_event.to_parquet(per_event_path, index=False)
    manifest = build_run_manifest(config, content_hash(config.distance_matrix))
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    await get_engine().dispose()
    print(
        f"Wrote {len(per_run)} per-run rows -> {per_run_path}\n"
        f"Wrote {len(per_event)} per-event rows -> {per_event_path}\n"
        f"Wrote manifest -> {manifest_path}"
    )


def _parse_algorithms(values: list[str]) -> list[AlgorithmName]:
    """Parse algorithm names from the CLI into the enum (validates spelling)."""
    return [AlgorithmName(value) for value in values]


def main() -> None:
    """CLI entry point for the batch grid runner (RB-6), or reproduction from a manifest (RB-10)."""
    parser = argparse.ArgumentParser(description="Run the EBADS simulation evaluation grid.")
    parser.add_argument(
        "--from-manifest",
        type=Path,
        default=None,
        help="Reproduce a grid from a run manifest (RB-10); ignores the grid flags below.",
    )
    parser.add_argument("--study-id", help="Study identifier / output subfolder.")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Base seed (default study).")
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=[a.value for a in AlgorithmName],
        help="Algorithms to sweep (default: all three).",
    )
    parser.add_argument(
        "--occupancies",
        nargs="+",
        type=float,
        default=list(OCCUPANCY_SCENARIOS),
        help="Occupancy scenarios to sweep (default: 0.75 0.90 1.00).",
    )
    parser.add_argument("--runs", type=int, default=RUNS_PER_CONFIGURATION, help="Runs per cell.")
    parser.add_argument("--events", type=int, default=EVENTS_PER_RUN, help="Events per run.")
    parser.add_argument(
        "--distance-matrix", type=Path, help="Precomputed matrix Parquet (RB-4)."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("artifacts/sim"), help="Output root directory."
    )
    args = parser.parse_args()

    if args.from_manifest is not None:
        config = grid_config_from_manifest(args.from_manifest, args.out_dir)
    else:
        if args.study_id is None or args.distance_matrix is None:
            parser.error("--study-id and --distance-matrix are required unless --from-manifest")
        config = GridConfig(
            study_id=args.study_id,
            base_seed=args.seed,
            algorithms=_parse_algorithms(args.algorithms),
            occupancies=args.occupancies,
            runs=args.runs,
            events=args.events,
            distance_matrix=args.distance_matrix,
            out_dir=args.out_dir,
        )
    asyncio.run(_main(config))


if __name__ == "__main__":
    main()
