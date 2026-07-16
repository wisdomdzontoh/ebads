"""Precomputed travel-time matrix for the simulation (docs/07-simulation.md §3, RB-4).

Large, reproducible runs cannot afford a live maps call per event, so travel times during
simulation are served from a matrix precomputed once over a regular grid of patient sample
points across ``GA_BBOX`` and the registered facilities. ``MatrixTravelTimeService`` presents
the same ``TravelTimeService`` interface as the live service — each simulated patient snaps
to its nearest grid node and the answer is a table lookup, with no network I/O and therefore
no non-determinism (docs/13 troubleshooting: "ensure distance matrix is used in sim").

The build may call the real Distance Matrix API (bounded to grid x facilities calls) when a
key is configured, or fall back to Haversine at 30 km/h otherwise; the matrix records which
source was used (docs/07 §3) and is content-hashed so results can cite the exact instrument
(docs/07 §9).

CLI (RB-4)::

    python -m app.simulation.distance_matrix build \
      --facilities data/ga_facilities.csv --out artifacts/distance_matrix.parquet
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import get_settings
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import DISTANCE_MATRIX_GRID_SIZE, GA_BBOX


@dataclass(frozen=True)
class DistanceMatrix:
    """A precomputed (grid node x facility) travel-time table in minutes (docs/07 §3).

    ``node_coords`` are the ``K`` patient grid points, ``facility_coords`` the ``F`` facility
    points (aligned with ``facility_ids``), and ``minutes`` the ``K x F`` travel times.
    ``is_estimated`` is a whole-matrix flag: true when the Haversine fallback was used for the
    build (no/failed maps key). ``content_hash`` identifies the persisted file (docs/07 §9).
    """

    node_coords: np.ndarray  # shape (K, 2): [lat, lon]
    facility_ids: list[str]
    facility_coords: np.ndarray  # shape (F, 2): [lat, lon]
    minutes: np.ndarray  # shape (K, F)
    source: str  # "google" | "haversine"
    is_estimated: bool
    seed: int
    grid_size: tuple[int, int]
    bbox: tuple[float, float, float, float]
    content_hash: str = ""


def grid_nodes(
    bbox: tuple[float, float, float, float], grid_size: tuple[int, int]
) -> np.ndarray:
    """Return the ``rows*cols`` regular grid points spanning ``bbox`` as an ``(K, 2)`` array.

    A regular grid (rather than random sampling) makes the node set itself deterministic and
    the nearest-node snap well defined; the seed governs where simulated patients fall, and
    each falls to its nearest node here (docs/07 §3).
    """
    lat_min, lat_max, lon_min, lon_max = bbox
    rows, cols = grid_size
    lats = np.linspace(lat_min, lat_max, rows)
    lons = np.linspace(lon_min, lon_max, cols)
    mesh_lat, mesh_lon = np.meshgrid(lats, lons, indexing="ij")
    return np.column_stack([mesh_lat.ravel(), mesh_lon.ravel()])


async def build_distance_matrix(
    facilities: list[tuple[str, float, float]],
    travel_service: TravelTimeService,
    seed: int = 0,
    grid_size: tuple[int, int] = DISTANCE_MATRIX_GRID_SIZE,
    bbox: tuple[float, float, float, float] = GA_BBOX,
) -> DistanceMatrix:
    """Build the full grid-node x facility travel-time matrix (docs/07 §3).

    Calls ``travel_service`` once per (node, facility) cell. The whole matrix is flagged
    ``is_estimated`` (and ``source = "haversine"``) if *any* cell fell back to the estimate,
    else ``source = "google"`` — an honest single-label record of which source was used.
    """
    nodes = grid_nodes(bbox, grid_size)
    facility_ids = [name for name, _, _ in facilities]
    facility_coords = np.array([[lat, lon] for _, lat, lon in facilities], dtype=float)

    minutes = np.zeros((len(nodes), len(facilities)), dtype=float)
    any_estimated = False
    for node_index, (node_lat, node_lon) in enumerate(nodes):
        origin = Coordinate(float(node_lat), float(node_lon))
        for facility_index, (_, fac_lat, fac_lon) in enumerate(facilities):
            result = await travel_service.travel_time(origin, Coordinate(fac_lat, fac_lon))
            minutes[node_index, facility_index] = result.minutes
            any_estimated = any_estimated or result.is_estimated

    return DistanceMatrix(
        node_coords=nodes,
        facility_ids=facility_ids,
        facility_coords=facility_coords,
        minutes=minutes,
        source="haversine" if any_estimated else "google",
        is_estimated=any_estimated,
        seed=seed,
        grid_size=grid_size,
        bbox=bbox,
    )


def _to_dataframe(matrix: DistanceMatrix) -> pd.DataFrame:
    """Flatten the matrix into a tidy one-row-per-(node, facility) table for Parquet."""
    rows: list[dict[str, object]] = []
    for node_index, (node_lat, node_lon) in enumerate(matrix.node_coords):
        for facility_index, facility_id in enumerate(matrix.facility_ids):
            fac_lat, fac_lon = matrix.facility_coords[facility_index]
            rows.append(
                {
                    "node_index": node_index,
                    "node_lat": float(node_lat),
                    "node_lon": float(node_lon),
                    "facility_index": facility_index,
                    "facility_id": facility_id,
                    "facility_lat": float(fac_lat),
                    "facility_lon": float(fac_lon),
                    "minutes": float(matrix.minutes[node_index, facility_index]),
                    # Constant provenance columns (docs/07 §3, §9) — same on every row.
                    "source": matrix.source,
                    "is_estimated": matrix.is_estimated,
                    "seed": matrix.seed,
                    "grid_rows": matrix.grid_size[0],
                    "grid_cols": matrix.grid_size[1],
                }
            )
    return pd.DataFrame(rows)


def content_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of the file's bytes (the matrix's identity, docs/07 §9)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_distance_matrix(matrix: DistanceMatrix, path: Path) -> str:
    """Write the matrix to ``path`` as Parquet and return its content hash (docs/07 §9)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _to_dataframe(matrix).to_parquet(path, index=False)
    return content_hash(path)


def load_distance_matrix(path: Path) -> DistanceMatrix:
    """Reconstruct a :class:`DistanceMatrix` from a Parquet file written by ``save``."""
    frame = pd.read_parquet(path)
    node_count = int(frame["node_index"].max()) + 1
    facility_count = int(frame["facility_index"].max()) + 1

    node_coords = np.zeros((node_count, 2), dtype=float)
    facility_coords = np.zeros((facility_count, 2), dtype=float)
    minutes = np.zeros((node_count, facility_count), dtype=float)
    facility_ids: list[str] = [""] * facility_count
    for record in frame.itertuples(index=False):
        node_coords[record.node_index] = [record.node_lat, record.node_lon]
        facility_coords[record.facility_index] = [record.facility_lat, record.facility_lon]
        facility_ids[record.facility_index] = str(record.facility_id)
        minutes[record.node_index, record.facility_index] = record.minutes

    first = frame.iloc[0]
    return DistanceMatrix(
        node_coords=node_coords,
        facility_ids=facility_ids,
        facility_coords=facility_coords,
        minutes=minutes,
        source=str(first["source"]),
        is_estimated=bool(first["is_estimated"]),
        seed=int(first["seed"]),
        grid_size=(int(first["grid_rows"]), int(first["grid_cols"])),
        bbox=GA_BBOX,
        content_hash=content_hash(path),
    )


class MatrixTravelTimeService(TravelTimeService):
    """Serves travel times from a precomputed matrix via nearest-node lookup (docs/07 §3)."""

    def __init__(self, matrix: DistanceMatrix) -> None:
        self._matrix = matrix
        # Facilities are few and fixed, so cache each destination's resolved column.
        self._facility_index_cache: dict[tuple[float, float], int] = {}

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        """Return the matrix cell: nearest grid node to ``origin`` x facility ``destination``."""
        node_index = self._nearest_index(self._matrix.node_coords, origin)
        facility_index = self._nearest_facility_index(destination)
        minutes = float(self._matrix.minutes[node_index, facility_index])
        return TravelTimeResult(minutes=minutes, is_estimated=self._matrix.is_estimated)

    @staticmethod
    def _nearest_index(coords: np.ndarray, point: Coordinate) -> int:
        """Index of the row in ``coords`` closest (squared Euclidean) to ``point``."""
        deltas = coords - np.array([point.latitude, point.longitude])
        return int(np.argmin(np.einsum("ij,ij->i", deltas, deltas)))

    def _nearest_facility_index(self, destination: Coordinate) -> int:
        key = (round(destination.latitude, 6), round(destination.longitude, 6))
        cached = self._facility_index_cache.get(key)
        if cached is None:
            cached = self._nearest_index(self._matrix.facility_coords, destination)
            self._facility_index_cache[key] = cached
        return cached


def _read_facilities_csv(path: Path) -> list[tuple[str, float, float]]:
    """Read (name, latitude, longitude) triples from the facility CSV (RB-4 ``--facilities``)."""
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            (row["name"].strip(), float(row["latitude"]), float(row["longitude"]))
            for row in csv.DictReader(handle)
        ]


async def _build_cli(facilities_path: Path, out_path: Path, seed: int) -> None:
    """RB-4 body: read facilities, build the matrix, persist it, and report provenance."""
    facilities = _read_facilities_csv(facilities_path)
    travel_service = LiveTravelTimeService(get_settings().google_maps_api_key)
    matrix = await build_distance_matrix(facilities, travel_service, seed=seed)
    digest = save_distance_matrix(matrix, out_path)
    print(
        f"Built distance matrix: {matrix.minutes.shape[0]} nodes x "
        f"{matrix.minutes.shape[1]} facilities; source={matrix.source}; "
        f"is_estimated={matrix.is_estimated}; sha256={digest}; out={out_path}"
    )


def main() -> None:
    """CLI entry point for building the distance matrix (RB-4)."""
    parser = argparse.ArgumentParser(description="Build the EBADS simulation distance matrix.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="Build and persist the distance matrix.")
    build.add_argument("--facilities", required=True, type=Path, help="Facility CSV path.")
    build.add_argument("--out", required=True, type=Path, help="Output Parquet path.")
    build.add_argument(
        "--seed", type=int, default=0, help="Recorded provenance seed (default 0)."
    )
    args = parser.parse_args()
    if args.command == "build":
        asyncio.run(_build_cli(args.facilities, args.out, args.seed))


if __name__ == "__main__":
    main()
