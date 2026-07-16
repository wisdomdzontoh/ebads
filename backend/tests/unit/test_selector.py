"""Dynamic selector tests (docs/12-testing.md §3, docs/03 §8)."""

from __future__ import annotations

import pytest

from app.domain.allocation.selector import select_algorithm
from app.parameters import AlgorithmName, Urgency


@pytest.mark.parametrize("urgency", list(Urgency))
def test_live_with_urgency_uses_urgency_adaptive(urgency: Urgency) -> None:
    assert select_algorithm(None, urgency) == AlgorithmName.URGENCY_ADAPTIVE


def test_live_without_urgency_falls_back_to_weighted() -> None:
    assert select_algorithm(None, None) == AlgorithmName.WEIGHTED


@pytest.mark.parametrize("configured", list(AlgorithmName))
def test_simulation_uses_session_algorithm(configured: AlgorithmName) -> None:
    # A simulation session's configured algorithm always wins, even greedy.
    assert select_algorithm(configured, Urgency.CRITICAL) == configured


def test_greedy_is_only_reachable_inside_simulation() -> None:
    # No live path (session_algorithm=None) ever returns greedy.
    for urgency in (*Urgency, None):
        assert select_algorithm(None, urgency) != AlgorithmName.GREEDY
