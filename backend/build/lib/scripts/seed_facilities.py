"""Idempotent facility seeding script (docs/11-development-setup.md §5, RB-2).

Loads the Greater Accra facility set from a CSV into the registry. Facilities are upserted
by name, so re-running does not create duplicates. For each supported bed type the script
sets a live ``bed_count`` row with ``available = capacity`` — the live registry starts fully
available; simulation seeds its own isolated occupancy separately (docs/02 §4). [IMPL]

Run inside the engine container::

    python -m scripts.seed_facilities --source data/ga_facilities.csv

CSV columns:
    name, latitude, longitude, tier, supported_bed_types,
    capacity_general, capacity_icu, capacity_maternity_specialist, contact_phone
where ``supported_bed_types`` is a ``|``-separated list (e.g. ``general|icu``).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.db.session import get_engine, get_sessionmaker
from app.parameters import BedType, DataSource, Tier

# Maps a bed type to the CSV column that carries its capacity.
_CAPACITY_COLUMN: dict[BedType, str] = {
    BedType.GENERAL: "capacity_general",
    BedType.ICU: "capacity_icu",
    BedType.MATERNITY_SPECIALIST: "capacity_maternity_specialist",
}


def _parse_row(row: dict[str, str]) -> tuple[Facility, dict[BedType, int]]:
    """Turn one CSV row into an (unsaved) Facility plus its capacity-per-bed-type map."""
    supported = [BedType(value) for value in row["supported_bed_types"].split("|") if value]
    capacities = {bed_type: int(row[_CAPACITY_COLUMN[bed_type]]) for bed_type in supported}
    facility = Facility(
        name=row["name"].strip(),
        latitude=Decimal(row["latitude"]),
        longitude=Decimal(row["longitude"]),
        tier=Tier(row["tier"].strip()),
        supported_bed_types=supported,
        contact_phone=row["contact_phone"].strip(),
        active_data_source=DataSource.SIMULATION,
    )
    return facility, capacities


def _apply_bed_counts(facility: Facility, capacities: dict[BedType, int]) -> None:
    """Upsert each supported bed type's count on ``facility`` with available == capacity."""
    existing = {bc.bed_type: bc for bc in facility.bed_counts}
    for bed_type, capacity in capacities.items():
        if bed_type in existing:
            existing[bed_type].available = capacity
            existing[bed_type].capacity = capacity
        else:
            facility.bed_counts.append(
                BedCount(bed_type=bed_type, available=capacity, capacity=capacity)
            )


async def _seed(session: AsyncSession, rows: list[dict[str, str]]) -> int:
    """Upsert every CSV row, returning the total facility count after seeding."""
    for row in rows:
        parsed, capacities = _parse_row(row)
        current = await session.scalar(select(Facility).where(Facility.name == parsed.name))
        if current is None:
            session.add(parsed)
            _apply_bed_counts(parsed, capacities)
        else:
            current.latitude = parsed.latitude
            current.longitude = parsed.longitude
            current.tier = parsed.tier
            current.supported_bed_types = parsed.supported_bed_types
            current.contact_phone = parsed.contact_phone
            current.active_data_source = parsed.active_data_source
            _apply_bed_counts(current, capacities)
    await session.commit()
    total = await session.scalar(select(func.count()).select_from(Facility))
    return int(total or 0)


async def _main(source: Path) -> None:
    """Read the CSV and run the seed within a single session/transaction."""
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    async with get_sessionmaker()() as session:
        total = await _seed(session, rows)
    await get_engine().dispose()
    print(f"Seeded {len(rows)} rows; registry now holds {total} facilities.")


def main() -> None:
    """CLI entry point: parse ``--source`` and run the async seeding routine."""
    parser = argparse.ArgumentParser(description="Seed the EBADS facility registry from CSV.")
    parser.add_argument("--source", required=True, type=Path, help="Path to the facility CSV.")
    args = parser.parse_args()
    asyncio.run(_main(args.source))


if __name__ == "__main__":
    main()
