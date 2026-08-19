"""Reservation fall-through unit tests (docs/01 §7, FR9).

A fake ``BedDataSource`` that records every ``reserve`` call lets this prove the fall-through
*and* the "no re-query" claim without a database: FR9's accept criterion is that a forced
version conflict produces a second attempt against candidate #2 with no repeat spatial
query — here, that means the ranking passed in is never touched again, only ``reserve`` is
called, once per candidate, in ranked order.
"""

from __future__ import annotations

import uuid

from app.domain.allocation.candidate import Candidate, ScoredCandidate
from app.domain.beds.base import BedDataSource, BedState, HealthStatus, VersionConflict
from app.domain.reservation.manager import reserve_from_ranking
from app.parameters import BedType, Tier


class _FakeBedSource(BedDataSource):
    """Conflicts on every facility_id in ``conflicting_ids``; succeeds otherwise."""

    def __init__(self, conflicting_ids: set[str]) -> None:
        self._conflicting_ids = conflicting_ids
        self.reserve_calls: list[tuple[str, int]] = []

    def name(self) -> str:
        return "fake"

    async def fetch(self, facility_id: uuid.UUID) -> list[BedState]:
        raise NotImplementedError("not exercised by this test")

    async def reserve(
        self, facility_id: uuid.UUID, bed_type: BedType, expect_version: int
    ) -> None:
        self.reserve_calls.append((str(facility_id), expect_version))
        if str(facility_id) in self._conflicting_ids:
            raise VersionConflict(f"{facility_id} conflicted")

    async def release(self, facility_id: uuid.UUID, bed_type: BedType) -> None:
        raise NotImplementedError("not exercised by this test")

    async def health(self) -> HealthStatus:
        return HealthStatus(healthy=True)


def _scored(facility_id: str, score: float, version: int = 0) -> ScoredCandidate:
    candidate = Candidate(
        facility_id=facility_id,
        tier=Tier.TERTIARY,
        travel_time_min=10.0,
        available_beds=1,
        version=version,
    )
    return ScoredCandidate(candidate=candidate, t_hat=0.0, b_hat=0.0, c_hat=1.0, score=score)


_FACILITY_A = str(uuid.uuid4())
_FACILITY_B = str(uuid.uuid4())
_FACILITY_C = str(uuid.uuid4())


async def test_first_candidate_succeeds_with_no_fallthrough() -> None:
    source = _FakeBedSource(conflicting_ids=set())
    ranked = [_scored(_FACILITY_A, score=0.1), _scored(_FACILITY_B, score=0.5)]

    result = await reserve_from_ranking(source, ranked, BedType.ICU)

    assert result.reserved is not None
    assert result.reserved.candidate.facility_id == _FACILITY_A
    assert result.attempts == 1
    assert source.reserve_calls == [(_FACILITY_A, 0)]


async def test_conflict_falls_through_to_next_ranked_candidate() -> None:
    """FR9: candidate #1 conflicts, #2 succeeds — exactly one attempt each, in rank order."""
    source = _FakeBedSource(conflicting_ids={_FACILITY_A})
    ranked = [
        _scored(_FACILITY_A, score=0.1, version=3),
        _scored(_FACILITY_B, score=0.5, version=7),
    ]

    result = await reserve_from_ranking(source, ranked, BedType.ICU)

    assert result.reserved is not None
    assert result.reserved.candidate.facility_id == _FACILITY_B
    assert result.attempts == 2
    # Each candidate's OWN captured version was used — no re-fetch (FR9).
    assert source.reserve_calls == [(_FACILITY_A, 3), (_FACILITY_B, 7)]


async def test_ranking_order_is_by_score_not_input_order() -> None:
    """The manager ranks before attempting — an out-of-order input list is still tried

    lowest-score-first (docs/03 §9's tie-break), so the caller's own ordering never matters.
    """
    source = _FakeBedSource(conflicting_ids=set())
    unordered = [_scored(_FACILITY_C, score=0.9), _scored(_FACILITY_A, score=0.1)]

    result = await reserve_from_ranking(source, unordered, BedType.ICU)

    assert result.reserved is not None
    assert result.reserved.candidate.facility_id == _FACILITY_A
    assert result.attempts == 1


async def test_every_candidate_conflicting_exhausts_with_none_reserved() -> None:
    source = _FakeBedSource(conflicting_ids={_FACILITY_A, _FACILITY_B})
    ranked = [_scored(_FACILITY_A, score=0.1), _scored(_FACILITY_B, score=0.5)]

    result = await reserve_from_ranking(source, ranked, BedType.ICU)

    assert result.reserved is None
    assert result.attempts == 2


async def test_empty_ranking_reserves_nothing() -> None:
    source = _FakeBedSource(conflicting_ids=set())
    result = await reserve_from_ranking(source, [], BedType.ICU)
    assert result.reserved is None
    assert result.attempts == 0
    assert source.reserve_calls == []
