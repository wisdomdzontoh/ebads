"""Precomputed distance matrix (docs/07-simulation.md §3, §9).

Verifies the build (shape, Haversine source flag), the Parquet round-trip and content hash
(the matrix's recorded identity), and that ``MatrixTravelTimeService`` serves the correct
cell via nearest-node/nearest-facility lookup and propagates the estimated flag.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.domain.travel.base import Coordinate
from app.domain.travel.live import LiveTravelTimeService
from app.simulation.distance_matrix import (
    DistanceMatrix,
    MatrixTravelTimeService,
    build_distance_matrix,
    grid_nodes,
    load_distance_matrix,
    save_distance_matrix,
)

_FACILITIES = [
    ("Korle Bu", 5.5366, -0.2261),
    ("37 Military", 5.5826, -0.1880),
    ("Tema General", 5.6698, -0.0166),
]


async def _haversine_matrix(grid: tuple[int, int] = (6, 6)) -> DistanceMatrix:
    """Build a small Haversine-only matrix for the fixed facility set."""
    return await build_distance_matrix(
        _FACILITIES, LiveTravelTimeService(""), seed=42, grid_size=grid
    )


def test_grid_nodes_count_matches_grid_size() -> None:
    """A (rows x cols) grid produces exactly rows*cols nodes spanning the box corners."""
    nodes = grid_nodes((5.45, 5.95, -0.45, 0.25), (4, 7))
    assert nodes.shape == (28, 2)
    assert nodes[:, 0].min() == 5.45 and nodes[:, 0].max() == 5.95
    assert nodes[:, 1].min() == -0.45 and nodes[:, 1].max() == 0.25


async def test_build_shape_and_haversine_flag() -> None:
    """No API key => every cell estimated => whole matrix flagged Haversine (docs/07 §3)."""
    matrix = await _haversine_matrix((6, 6))
    assert matrix.minutes.shape == (36, len(_FACILITIES))
    assert matrix.is_estimated is True
    assert matrix.source == "haversine"
    assert matrix.facility_ids == [name for name, _, _ in _FACILITIES]


async def test_parquet_round_trip_and_content_hash(tmp_path: Path) -> None:
    """Saving then loading reconstructs the arrays and a stable content hash (docs/07 §9)."""
    matrix = await _haversine_matrix((6, 6))
    path = tmp_path / "distance_matrix.parquet"
    saved_hash = save_distance_matrix(matrix, path)

    loaded = load_distance_matrix(path)
    assert loaded.content_hash == saved_hash
    assert loaded.facility_ids == matrix.facility_ids
    assert np.allclose(loaded.minutes, matrix.minutes)
    assert np.allclose(loaded.node_coords, matrix.node_coords)
    assert loaded.is_estimated is True


async def test_service_returns_nearest_node_facility_cell(tmp_path: Path) -> None:
    """The service resolves (nearest node, nearest facility) and returns that matrix cell."""
    matrix = await _haversine_matrix((6, 6))
    path = tmp_path / "distance_matrix.parquet"
    save_distance_matrix(matrix, path)
    service = MatrixTravelTimeService(load_distance_matrix(path))

    origin = Coordinate(5.60, -0.19)
    destination = Coordinate(*_FACILITIES[1][1:])  # exactly 37 Military's coordinates
    result = await service.travel_time(origin, destination)

    node_index = service._nearest_index(matrix.node_coords, origin)
    assert abs(result.minutes - float(matrix.minutes[node_index, 1])) < 1e-9
    assert result.is_estimated is True
