"""Grid seed derivation (docs/07-simulation.md §7).

The paired statistical design requires that, at a given (occupancy, run index), every
algorithm sees the identical event stream — i.e. the seed must depend on occupancy and run
index but **not** the algorithm. ``derive_seed`` takes no algorithm argument by design; these
tests lock in determinism, algorithm-independence (structurally), and distinct seeds across
grid cells.
"""

from __future__ import annotations

from app.simulation.runner import derive_seed


def test_seed_is_deterministic() -> None:
    """The same (base, occupancy index, run index) always yields the same seed."""
    assert derive_seed(20260617, 1, 7) == derive_seed(20260617, 1, 7)


def test_seed_pairs_across_occupancy_and_run_index() -> None:
    """Two grid cells sharing (occupancy index, run index) share a seed — the pairing key.

    Because ``derive_seed`` has no algorithm parameter, any two algorithms at the same cell
    necessarily use the same seed and therefore the same generated events (docs/07 §7).
    """
    cell = (0, 12)
    assert derive_seed(20260617, *cell) == derive_seed(20260617, *cell)


def test_distinct_cells_get_distinct_seeds() -> None:
    """Every (occupancy index, run index) in a realistic grid maps to a unique seed."""
    seeds = {
        derive_seed(20260617, occupancy_index, run_index)
        for occupancy_index in range(3)
        for run_index in range(30)
    }
    assert len(seeds) == 3 * 30  # no collisions across the 90 (occupancy, run) cells


def test_different_occupancy_indices_do_not_overlap_within_a_run_budget() -> None:
    """Occupancy seed bands stay disjoint for run indices far below the stride."""
    assert derive_seed(0, 0, 29) != derive_seed(0, 1, 0)
