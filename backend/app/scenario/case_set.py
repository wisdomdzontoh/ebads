"""Fixed case set loader (docs/07-scenario-testing.md §4, FR23).

A case set is a version-controlled JSON file, loaded not generated — there is no sampling
here, deliberately. Each case supplies exactly what a dispatcher would enter: an origin,
an urgency, and a required bed type. Cases are returned in file order, which the docs treat
as part of the fixture (§4: "Order is part of the fixture") because later cases in a
depleting-bed-state replay are constrained by earlier ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.parameters import BedType, Urgency


class CaseSetError(Exception):
    """Raised when a case-set file is missing a required field or names an unknown value."""


@dataclass(frozen=True)
class Case:
    """One scenario case (docs/07 §4)."""

    case_id: str
    origin_lat: float
    origin_lon: float
    urgency: Urgency
    required_bed_type: BedType


def load_cases(path: str | Path) -> list[Case]:
    """Load a fixed, ordered case set from ``path``.

    Raises :class:`CaseSetError` on a malformed entry — fail loudly rather than silently
    skip a case, since case-set integrity is what makes a run reproducible and complete.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise CaseSetError(f"{path}: expected a non-empty JSON array of cases")

    cases: list[Case] = []
    seen_ids: set[str] = set()
    for i, entry in enumerate(raw):
        try:
            case = Case(
                case_id=str(entry["case_id"]),
                origin_lat=float(entry["origin_lat"]),
                origin_lon=float(entry["origin_lon"]),
                urgency=Urgency(entry["urgency"]),
                required_bed_type=BedType(entry["required_bed_type"]),
            )
        except (KeyError, ValueError) as exc:
            raise CaseSetError(f"{path}: case at index {i} is invalid: {exc}") from exc
        if case.case_id in seen_ids:
            raise CaseSetError(f"{path}: duplicate case_id {case.case_id!r}")
        seen_ids.add(case.case_id)
        cases.append(case)
    return cases
