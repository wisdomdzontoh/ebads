"""PostGIS spatial retrieval (docs/01 §2, docs/03 §2, FR3, NFR2).

Proves the two things FR3/NFR2 actually require: the retrieval query plan uses the GIST
index rather than a sequential scan, and the retrieval is correct (includes facilities
within the urgency radius, excludes those outside it). A sequential scan only shows up as a
defect once a table has enough rows that Postgres's planner would actually prefer an index —
too few rows and the planner correctly (and unhelpfully, for this test) prefers a scan
regardless of the index's existence, so this seeds a few hundred synthetic facilities.
"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement, Executable

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.domain.allocation.service import AllocationService
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.parameters import BedType, Tier

# Accra city-centre-ish origin; facilities are scattered around it.
_ORIGIN_LAT, _ORIGIN_LON = 5.6037, -0.1870


class _Explain(Executable, ClauseElement):
    """Wraps a SELECT as ``EXPLAIN <select>`` (SQLAlchemy's own recipe for this).

    Compiling via ``compiler.process(element.statement)`` — rather than recompiling with
    ``literal_binds`` or reaching for ``prefix_with`` (which inserts *after* SELECT, not
    before the whole statement) — routes every bind parameter through its normal type's
    bind processor, so the Geography-typed origin point is handled exactly as it is for the
    real query.
    """

    inherit_cache = True

    def __init__(self, statement: Select[Any]) -> None:
        self.statement = statement


@compiles(_Explain)
def _compile_explain(element: _Explain, compiler: Any, **kw: Any) -> str:
    return "EXPLAIN " + compiler.process(element.statement, **kw)


class _StubTravel(TravelTimeService):
    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=5.0, is_estimated=False)


async def _seed_scattered_facilities(session: AsyncSession, count: int = 300) -> None:
    """Scatter ``count`` facilities on a grid spanning roughly +-1 degree (~110 km) around

    the origin, each with one available ICU bed — enough rows and enough spatial spread for
    the planner to prefer the GIST index over a sequential scan.
    """
    side = math.ceil(math.sqrt(count))
    step = 2.0 / side
    created = 0
    for i in range(side):
        for j in range(side):
            if created >= count:
                break
            lat = _ORIGIN_LAT - 1.0 + i * step
            lon = _ORIGIN_LON - 1.0 + j * step
            facility = Facility(
                name=f"Scattered Facility {created}",
                latitude=str(round(lat, 6)),
                longitude=str(round(lon, 6)),
                tier=Tier.TERTIARY,
                supported_bed_types=[BedType.ICU],
                contact_phone="+233000000000",
            )
            session.add(facility)
            await session.flush()
            session.add(
                BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=1, capacity=1)
            )
            created += 1
    await session.commit()


async def test_spatial_retrieval_query_uses_the_gist_index(db_session: AsyncSession) -> None:
    """FR3's accept criterion: EXPLAIN shows index usage, not a sequential scan."""
    await _seed_scattered_facilities(db_session, count=300)
    # A freshly bulk-inserted table has no planner statistics yet — without ANALYZE, the
    # planner may still guess a sequential scan regardless of the index (it doesn't yet
    # know the table has 300 rows, not the near-empty default it assumes for a new table).
    await db_session.execute(text("ANALYZE facility"))

    origin = Coordinate(_ORIGIN_LAT, _ORIGIN_LON)
    query = AllocationService.spatial_retrieve_query(
        origin, radius_minutes=30.0, bed_type=BedType.ICU
    )
    result = await db_session.execute(_Explain(query))
    plan_text = "\n".join(row[0] for row in result.all())

    assert "Seq Scan on facility" not in plan_text, plan_text
    assert "Index Scan" in plan_text or "Bitmap Index Scan" in plan_text, plan_text


async def test_spatial_retrieval_includes_within_radius_excludes_outside(
    db_session: AsyncSession,
) -> None:
    """Correctness alongside the index proof: radius boundary behaves as documented."""
    near = Facility(
        name="Near Facility",
        latitude="5.61",
        longitude="-0.19",  # ~1.4 km from origin — well within a 30 min / 15 km radius
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    far = Facility(
        name="Far Facility",
        latitude="6.60",
        longitude="-1.19",  # >100 km away — well outside any urgency radius
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233000000000",
    )
    db_session.add_all([near, far])
    await db_session.flush()
    db_session.add(BedCount(facility_id=near.id, bed_type=BedType.ICU, available=1, capacity=1))
    db_session.add(BedCount(facility_id=far.id, bed_type=BedType.ICU, available=1, capacity=1))
    await db_session.commit()

    service = AllocationService(db_session, _StubTravel())
    origin = Coordinate(_ORIGIN_LAT, _ORIGIN_LON)
    results = await service._spatial_retrieve(origin, radius_minutes=30.0, bed_type=BedType.ICU)

    ids = {f.id for f in results}
    assert near.id in ids
    assert far.id not in ids
