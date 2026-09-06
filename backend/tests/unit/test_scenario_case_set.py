"""``app/scenario/case_set.py`` — the fixed case-set loader (docs/07-scenario-testing.md §4)."""

from __future__ import annotations

import json

import pytest

from app.parameters import BedType, Urgency
from app.scenario.case_set import Case, CaseSetError, load_cases


def _write(tmp_path, name: str, content: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(content), encoding="utf-8")
    return str(path)


def test_loads_cases_in_file_order(tmp_path) -> None:
    path = _write(
        tmp_path,
        "cases.json",
        [
            {
                "case_id": "C001",
                "origin_lat": 5.6037,
                "origin_lon": -0.1870,
                "urgency": "critical",
                "required_bed_type": "icu",
            },
            {
                "case_id": "C002",
                "origin_lat": 5.5,
                "origin_lon": -0.2,
                "urgency": "standard",
                "required_bed_type": "general",
            },
        ],
    )
    cases = load_cases(path)
    assert cases == [
        Case("C001", 5.6037, -0.1870, Urgency.CRITICAL, BedType.ICU),
        Case("C002", 5.5, -0.2, Urgency.STANDARD, BedType.GENERAL),
    ]


def test_rejects_an_empty_case_set(tmp_path) -> None:
    path = _write(tmp_path, "cases.json", [])
    with pytest.raises(CaseSetError):
        load_cases(path)


def test_rejects_a_missing_field(tmp_path) -> None:
    path = _write(
        tmp_path,
        "cases.json",
        [{"case_id": "C001", "origin_lat": 5.6, "origin_lon": -0.2, "urgency": "critical"}],
    )
    with pytest.raises(CaseSetError):
        load_cases(path)


def test_rejects_an_unknown_urgency(tmp_path) -> None:
    path = _write(
        tmp_path,
        "cases.json",
        [
            {
                "case_id": "C001",
                "origin_lat": 5.6,
                "origin_lon": -0.2,
                "urgency": "extremely-critical",
                "required_bed_type": "general",
            }
        ],
    )
    with pytest.raises(CaseSetError):
        load_cases(path)


def test_rejects_a_duplicate_case_id(tmp_path) -> None:
    entry = {
        "case_id": "C001",
        "origin_lat": 5.6,
        "origin_lon": -0.2,
        "urgency": "critical",
        "required_bed_type": "general",
    }
    path = _write(tmp_path, "cases.json", [entry, dict(entry)])
    with pytest.raises(CaseSetError):
        load_cases(path)


def test_extra_fields_are_ignored(tmp_path) -> None:
    """A ``_note`` provenance field (used by data/case_sets/greater_accra_30.json) is fine."""
    path = _write(
        tmp_path,
        "cases.json",
        [
            {
                "case_id": "C001",
                "origin_lat": 5.6,
                "origin_lon": -0.2,
                "urgency": "critical",
                "required_bed_type": "general",
                "_note": "why this case exists",
            }
        ],
    )
    cases = load_cases(path)
    assert cases[0].case_id == "C001"


def test_real_case_set_loads_and_is_well_formed() -> None:
    """The actual fixture the scenario runner ships with (docs/07 §4: >= 8 escalations)."""
    cases = load_cases("data/case_sets/greater_accra_30.json")
    assert len(cases) == 30
    assert len({c.case_id for c in cases}) == 30
