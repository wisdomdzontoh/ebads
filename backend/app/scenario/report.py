"""Cross-strategy comparison report — the docs/07-scenario-testing.md §7 output artifacts.

Composes ``runner.py``'s raw per-case ``CaseRun``s into the thesis Table 3.10 comparison —
the three strategies under the default parameters, the same case set re-run under the
§3.8.4 robustness variant, and one contention-mode burst — then writes it as the three named
artifacts docs/07 §7 specifies, plus a fourth for the contention burst it does not cover:

- ``measures.csv`` — one row per (run, strategy, urgency tier, measure).
- ``decisions.jsonl`` — one line per case per (run, strategy): every ranked candidate with
  its t̂/b̂/ĉ/score, and which one was selected.
- ``manifest.json`` — the parameter snapshot, case-set and starting-state hashes, and the
  code commit. "facility-CSV hash" in docs/07 §7 refers to whatever fixture supplies static
  facility data; this implementation loads that from a JSON starting-state snapshot rather
  than the live registry's own loader input (``data/ga_facilities.csv`` — see ``runner.py``'s
  module docstring on why), so this hashes that file instead.
- ``contention.json`` — the contention-mode burst's attempts-per-case and double-booking
  count; docs/07 §7 predates this mode, so it names no file for it.

None of the four files carry a wall-clock timestamp — every one of them must be byte-for-
byte identical across two runs of the same case set and starting state, exactly like the
measures themselves (NFR6). Every replay happens in ``runner.py``; this module only shapes
and serialises results, so it never touches the database itself.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.allocation.study_parameters import StudyParameters
from app.parameters import ROBUSTNESS_CHECK_WEIGHTS, AlgorithmName, Urgency
from app.scenario.case_set import Case
from app.scenario.measures import CaseResult, MeasureSet, compute_measures, compute_measures_by_tier
from app.scenario.runner import (
    CaseRun,
    ContentionReport,
    FacilityState,
    run_all_strategies,
    run_contention_burst,
    run_robustness_check,
)

# thesis Table 3.10, in a fixed column order so measures.csv's row order is itself
# deterministic (dict/dataclass field order is already stable, but naming this once keeps
# the CSV writer and any future consumer honest about exactly which six there are).
_MEASURE_FIELDS: tuple[str, ...] = (
    "case_count",
    "placement_success",
    "escalation_rate",
    "mean_facility_attempts",
    "mean_travel_time_minutes",
    "mean_capability_match",
    "critical_at_tertiary_rate",
)


@dataclass(frozen=True)
class StrategyReport:
    """One strategy's measures under one run label, overall and per urgency tier."""

    run: str  # "primary" | "robustness" (docs/07 §7-8)
    algorithm: AlgorithmName
    overall: MeasureSet
    by_urgency: dict[Urgency, MeasureSet]
    case_runs: list[CaseRun]


@dataclass(frozen=True)
class ScenarioReport:
    """The complete comparison: primary run, robustness re-run, and the contention burst."""

    case_count: int
    strategy_reports: list[StrategyReport]
    contention: ContentionReport


def _case_result_from_run(run: CaseRun) -> CaseResult:
    return CaseResult(
        case_id=run.case.case_id,
        urgency=run.case.urgency,
        allocated=run.selected_facility_id is not None,
        travel_time_minutes=run.selected_travel_time_minutes,
        capability_match=run.selected_capability_match,
        tier=run.selected_tier,
        attempts=run.attempts,
    )


def _strategy_reports(
    run_label: str, results_by_algorithm: Mapping[AlgorithmName, list[CaseRun]]
) -> list[StrategyReport]:
    reports = []
    for algorithm, runs in results_by_algorithm.items():
        case_results = [_case_result_from_run(r) for r in runs]
        reports.append(
            StrategyReport(
                run=run_label,
                algorithm=algorithm,
                overall=compute_measures(case_results),
                by_urgency=compute_measures_by_tier(case_results),
                case_runs=runs,
            )
        )
    return reports


async def build_report(
    session: AsyncSession, cases: list[Case], starting_state: list[FacilityState]
) -> ScenarioReport:
    """Run the primary comparison, the robustness re-run, and the contention burst."""
    primary = await run_all_strategies(session, cases, starting_state)
    robustness = await run_robustness_check(session, cases, starting_state)
    contention = await run_contention_burst(session, cases, starting_state)
    return ScenarioReport(
        case_count=len(cases),
        strategy_reports=_strategy_reports("primary", primary)
        + _strategy_reports("robustness", robustness),
        contention=contention,
    )


def _measure_rows(
    run: str, algorithm: AlgorithmName, tier: str, measures: MeasureSet
) -> list[list[Any]]:
    return [
        [run, algorithm.value, tier, field, getattr(measures, field)] for field in _MEASURE_FIELDS
    ]


def write_measures_csv(report: ScenarioReport, path: Path) -> None:
    """``measures.csv`` — "one row per strategy per urgency tier per measure" (docs/07 §7)."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["run", "strategy", "urgency_tier", "measure", "value"])
        for sr in report.strategy_reports:
            for row in _measure_rows(sr.run, sr.algorithm, "overall", sr.overall):
                writer.writerow(row)
            for urgency in Urgency:
                tier_measures = sr.by_urgency[urgency]
                for row in _measure_rows(sr.run, sr.algorithm, urgency.value, tier_measures):
                    writer.writerow(row)


def _decision_line(run_label: str, algorithm: AlgorithmName, case_run: CaseRun) -> dict[str, Any]:
    return {
        "run": run_label,
        "algorithm": algorithm.value,
        "case_id": case_run.case.case_id,
        "urgency": case_run.case.urgency.value,
        "required_bed_type": case_run.case.required_bed_type.value,
        "status": case_run.status.value,
        "selection_reason": case_run.selection_reason,
        "selected_facility_id": case_run.selected_facility_id,
        "attempts": case_run.attempts,
        "candidates": [
            {
                "facility_id": c.facility_id,
                "tier": c.tier.value,
                "travel_time_min": c.travel_time_min,
                "available_beds": c.available_beds,
                "t_hat": c.t_hat,
                "b_hat": c.b_hat,
                "c_hat": c.c_hat,
                "score": c.score,
            }
            for c in case_run.candidates
        ],
    }


def write_decisions_jsonl(report: ScenarioReport, path: Path) -> None:
    """``decisions.jsonl`` — full decision trace per case (docs/07 §7)."""
    with path.open("w", encoding="utf-8") as f:
        for sr in report.strategy_reports:
            for case_run in sr.case_runs:
                f.write(json.dumps(_decision_line(sr.run, sr.algorithm, case_run), sort_keys=True))
                f.write("\n")


def _git_commit() -> str:
    """Best-effort current commit hash for the manifest — never fatal if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_manifest(
    case_set_path: str,
    starting_state_path: str,
    study_parameters: StudyParameters,
    case_count: int,
) -> dict[str, Any]:
    """``manifest.json`` — parameter snapshot, fixture hashes, code commit (docs/07 §7)."""
    return {
        "case_count": case_count,
        "case_set_sha256": _file_sha256(case_set_path),
        "starting_state_sha256": _file_sha256(starting_state_path),
        "code_commit": _git_commit(),
        "parameters": {
            "radius_minutes": {u.value: r for u, r in study_parameters.radius_minutes.items()},
            "capability_matrix": {
                u.value: {t.value: v for t, v in row.items()}
                for u, row in study_parameters.capability_matrix.items()
            },
            "weights_weighted": study_parameters.weights_weighted.model_dump(),
            "weights_urgency_adaptive": {
                u.value: w.model_dump()
                for u, w in study_parameters.weights_urgency_adaptive.items()
            },
            "robustness_weights_urgency_adaptive": {
                u.value: w.model_dump() for u, w in ROBUSTNESS_CHECK_WEIGHTS.items()
            },
        },
    }


def write_contention_json(report: ScenarioReport, path: Path) -> None:
    """``contention.json`` — attempts per case and the zero-double-booking count (FR8/FR9).

    Not one of docs/07 §7's three named files (that document predates contention mode);
    kept alongside them in the same study directory rather than folded into another file.
    """
    payload = {
        "algorithm": report.contention.algorithm.value,
        "double_bookings": report.contention.double_bookings,
        "cases": [
            {
                "case_id": c.case_id,
                "reserved_facility_name": c.reserved_facility_name,
                "attempts": c.attempts,
            }
            for c in report.contention.case_results
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def write_report(
    session: AsyncSession,
    cases: list[Case],
    starting_state: list[FacilityState],
    case_set_path: str,
    starting_state_path: str,
    output_dir: Path,
) -> ScenarioReport:
    """Run the full comparison and write ``measures.csv``, ``decisions.jsonl``,
    ``manifest.json``, and ``contention.json`` under ``output_dir`` (docs/07 §7).
    """
    report = await build_report(session, cases, starting_state)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_measures_csv(report, output_dir / "measures.csv")
    write_decisions_jsonl(report, output_dir / "decisions.jsonl")
    manifest = build_manifest(
        case_set_path, starting_state_path, StudyParameters.defaults(), len(cases)
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_contention_json(report, output_dir / "contention.json")
    return report
