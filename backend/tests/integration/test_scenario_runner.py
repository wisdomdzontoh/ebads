"""Scenario test runner integration tests (FR23, docs/07-scenario-testing.md, FR8/FR9).

Runs against the real Postgres/PostGIS test database (``db_session``, tests/integration/
conftest.py) — the scenario runner is a real client of the live allocation engine, so its
correctness can only be proven against the actual spatial retrieval + reservation CAS path,
not a mock.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.parameters import AlgorithmName, Status, Urgency
from app.scenario.case_set import load_cases
from app.scenario.report import build_report, write_report
from app.scenario.runner import (
    STRATEGIES,
    load_starting_state,
    run_all_strategies,
    run_contention_burst,
    truncate_owned_tables,
)

_CASE_SET = "data/case_sets/greater_accra_30.json"
_STARTING_STATE = "data/case_sets/greater_accra_30_starting_state.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


async def test_scenario_runner_is_deterministic(db_session: AsyncSession, tmp_path: Path) -> None:
    """Two consecutive runs of the same case set produce byte-identical output (NFR6) —
    every one of the four written artifacts, not just an in-memory measure."""
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    out_1 = tmp_path / "run1"
    out_2 = tmp_path / "run2"
    await write_report(db_session, cases, starting_state, _CASE_SET, _STARTING_STATE, out_1)
    await truncate_owned_tables(db_session)
    await write_report(db_session, cases, starting_state, _CASE_SET, _STARTING_STATE, out_2)

    for name in ("measures.csv", "decisions.jsonl", "manifest.json", "contention.json"):
        assert _read(out_1 / name) == _read(out_2 / name), f"{name} differs between runs"


async def test_all_three_strategies_run_from_an_identical_starting_state(
    db_session: AsyncSession,
) -> None:
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    results = await run_all_strategies(db_session, cases, starting_state)

    assert set(results) == set(STRATEGIES)
    for algorithm in STRATEGIES:
        assert len(results[algorithm]) == len(cases)
        # Every case_id from the fixture appears exactly once, in file order.
        assert [r.case.case_id for r in results[algorithm]] == [c.case_id for c in cases]


async def test_the_shipped_case_set_produces_at_least_eight_escalations(
    db_session: AsyncSession,
) -> None:
    """docs/07 §4: "at least eight cases with no admissible candidate" — verified, not assumed."""
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    results = await run_all_strategies(
        db_session, cases, starting_state, strategies=(AlgorithmName.URGENCY_ADAPTIVE,)
    )
    escalated = [r for r in results[AlgorithmName.URGENCY_ADAPTIVE] if r.status == Status.ESCALATED]
    assert len(escalated) >= 8


async def test_six_measures_are_reported_overall_and_per_urgency_tier(
    db_session: AsyncSession,
) -> None:
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    report = await build_report(db_session, cases, starting_state)
    primary = [sr for sr in report.strategy_reports if sr.run == "primary"]
    assert {sr.algorithm for sr in primary} == set(STRATEGIES)

    for strategy_report in primary:
        assert strategy_report.overall.case_count == len(cases)
        assert set(strategy_report.by_urgency) == set(Urgency)
        for urgency in Urgency:
            assert strategy_report.by_urgency[urgency].case_count >= 0


async def test_robustness_check_reruns_weighted_and_urgency_adaptive_only(
    db_session: AsyncSession,
) -> None:
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    report = await build_report(db_session, cases, starting_state)

    robustness_algorithms = {
        sr.algorithm for sr in report.strategy_reports if sr.run == "robustness"
    }
    assert robustness_algorithms == {AlgorithmName.WEIGHTED, AlgorithmName.URGENCY_ADAPTIVE}


async def test_contention_burst_reports_zero_double_bookings(db_session: AsyncSession) -> None:
    """A burst scored against one shared snapshot, then reserved in sequence (FR8/FR9)."""
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    contention = await run_contention_burst(db_session, cases, starting_state)

    assert contention.double_bookings == 0
    assert len(contention.case_results) == len(cases)
    # At least one case in the burst had to fall through past its first-ranked candidate —
    # otherwise this run never actually exercised contention at all.
    assert any(cr.attempts > 1 for cr in contention.case_results)


async def test_decisions_jsonl_has_one_line_per_case_per_strategy_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """docs/07 §7: "full decision trace per case (candidates, t̂/b̂/ĉ, scores, selection)"."""
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)
    out_dir = tmp_path / "study"

    await write_report(db_session, cases, starting_state, _CASE_SET, _STARTING_STATE, out_dir)

    lines = (out_dir / "decisions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    # 3 primary strategies + 2 robustness strategies, each replaying every case once.
    assert len(lines) == len(cases) * 5

    parsed = json.loads(lines[0])
    assert {"run", "algorithm", "case_id", "status", "candidates"} <= set(parsed)
    if parsed["candidates"]:
        candidate = parsed["candidates"][0]
        assert {"facility_id", "tier", "t_hat", "b_hat", "c_hat", "score"} <= set(candidate)


async def test_no_placement_is_within_one_minute_of_travel(db_session: AsyncSession) -> None:
    """Chapter Four evidence review, fix 1: every case origin was moved 1.5-4 km from the
    nearest facility so a placement never dispatches a patient to the building they are
    already inside. A zero-distance dispatch is not a meaningful emergency scenario."""
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)

    results = await run_all_strategies(db_session, cases, starting_state)

    for algorithm, runs in results.items():
        for run in runs:
            if run.selected_travel_time_minutes is not None:
                assert run.selected_travel_time_minutes >= 1.0, (
                    f"{algorithm.value}/{run.case.case_id} placed at "
                    f"{run.selected_travel_time_minutes} min"
                )


async def test_manifest_records_hashes_and_parameters(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    cases = load_cases(_CASE_SET)
    starting_state = load_starting_state(_STARTING_STATE)
    out_dir = tmp_path / "study"

    await write_report(db_session, cases, starting_state, _CASE_SET, _STARTING_STATE, out_dir)

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["case_count"] == len(cases)
    assert len(manifest["case_set_sha256"]) == 64
    assert len(manifest["starting_state_sha256"]) == 64
    assert "parameters" in manifest
    assert "robustness_weights_urgency_adaptive" in manifest["parameters"]
