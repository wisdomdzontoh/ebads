"""The compare-and-set reservation loop with fall-through (docs/01-architecture.md §7, FR8, FR9).

Given the already-ranked, already-scored candidate list from ``run_scoring`` (docs/03),
attempts ``reserve`` on each in order. A ``VersionConflict`` drops that candidate and moves
to the next — using the ``version`` each candidate already carries (captured at
``_build_candidates`` time, docs/02 §3.2), never a re-fetch or re-query. This is what FR9's
accept criterion asserts: a forced version conflict falls through to candidate #2 with no
repeat spatial query.

**Reads are advisory; the compare-and-set is authoritative** (docs/01 §7). A stale read
here costs one wasted attempt; it can never cause a double allocation, because
``BedDataSource.reserve`` is the single atomic write path (``domain/beds/manual_adapter.py``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.allocation.candidate import ScoredCandidate
from app.domain.allocation.scoring import rank_by_score
from app.domain.beds.base import BedDataSource, VersionConflict
from app.parameters import BedType


@dataclass(frozen=True)
class ReservationAttemptResult:
    """Outcome of attempting to reserve a bed from a ranked candidate list.

    ``reserved`` is ``None`` iff every candidate was tried and every one conflicted — a
    genuine race (all were claimed by concurrent requests between scoring and reserving),
    distinct from an empty candidate set (that never reaches this loop at all — docs/03 §1
    escalates before scoring when H_e is empty).
    """

    reserved: ScoredCandidate | None
    attempts: int


async def reserve_from_ranking(
    bed_source: BedDataSource, scored: list[ScoredCandidate], bed_type: BedType
) -> ReservationAttemptResult:
    """Try ``reserve`` on each candidate in ranked order; fall through on ``VersionConflict``."""
    attempts = 0
    for candidate in rank_by_score(scored):
        attempts += 1
        try:
            await bed_source.reserve(
                uuid.UUID(candidate.candidate.facility_id), bed_type, candidate.candidate.version
            )
        except VersionConflict:
            continue
        return ReservationAttemptResult(reserved=candidate, attempts=attempts)
    return ReservationAttemptResult(reserved=None, attempts=attempts)
