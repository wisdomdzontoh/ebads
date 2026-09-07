"""Chapter Four evidence — supplementary analysis (not part of app/scenario/'s own CLI).

Runs the two contention bursts docs/07 §7's own CLI does not produce (greedy, weighted —
it only bursts urgency_adaptive by default) via the *same* unmodified
``app.scenario.runner.run_contention_burst`` function the CLI itself calls; the R6 standard-
tier counterfactual (post-hoc diagnostic, evidence-review round 2) via the same unmodified
``run_scenario_for_strategy``; then computes several derived views over the canonical
``artifacts/scenario/<study_id>/`` output that the Chapter Four evidence brief asks for but
docs/07 §7 was never scoped to produce:

  - geographic reachability: for every case origin, which tertiary facilities (if any) are
    within the R(critical)=30 min radius, using the identical Haversine formula
    (``app.domain.travel.haversine``) the live engine itself uses;
  - tertiary capacity preservation: non-critical cases placed in a tertiary ICU bed, per
    primary-run strategy;
  - a cross-strategy per-case diff: every case where greedy/weighted/urgency_adaptive (primary
    run) chose a different facility, or a different one escalated;
  - travel-time distribution per strategy (min/median/mean/max, count > 45 min);
  - the standard-tier facility-size effect: every standard-urgency placement's chosen
    facility, its raw available-bed count, and its normalised b_hat.

Nothing here re-implements scoring, filtering, or reservation — every number is either read
straight from the CLI's own written artifacts or produced by calling the runner's own
functions unchanged. Writes one JSON file per output under ``analysis/raw/``.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import statistics
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("JWT_SECRET_KEY", "scratch-jwt-secret-key-at-least-32-bytes-long")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://ebads:ebads@localhost:5432/ebads_scenario"
)

from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.domain.allocation.study_parameters import StudyParameters  # noqa: E402
from app.domain.travel.base import Coordinate  # noqa: E402
from app.domain.travel.haversine import haversine_minutes  # noqa: E402
from app.parameters import (  # noqa: E402
    RADIUS_MINUTES,
    AlgorithmName,
    Urgency,
    WeightVector,
)
from app.scenario.case_set import load_cases  # noqa: E402
from app.scenario.measures import CaseResult, compute_measures_by_tier  # noqa: E402
from app.scenario.runner import (  # noqa: E402
    load_starting_state,
    populate_registry,
    reset_bed_state,
    run_contention_burst,
    run_scenario_for_strategy,
    truncate_owned_tables,
)

_STUDY_ID = "chapter4_2026-09-07_rev2"
_STUDY_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "scenario" / _STUDY_ID
_CASE_SET = _BACKEND / "data" / "case_sets" / "greater_accra_30.json"
_STARTING_STATE = _BACKEND / "data" / "case_sets" / "greater_accra_30_starting_state.json"
_RAW_DIR = Path(__file__).resolve().parent / "raw"


def _contention_report_to_dict(report: object) -> dict:
    from dataclasses import asdict

    d = asdict(report)  # type: ignore[call-overload]
    d["algorithm"] = report.algorithm.value  # type: ignore[attr-defined]
    return d


async def run_extra_contention_bursts() -> None:
    """R5's remaining two bursts (greedy, weighted) — urgency_adaptive already came from the
    CLI's own ``contention.json``. Each burst gets a freshly reset starting state, exactly as
    ``run_contention_burst`` itself does internally for its one call from the CLI."""
    cases = load_cases(str(_CASE_SET))
    starting_state = load_starting_state(str(_STARTING_STATE))

    async with get_sessionmaker()() as session:
        await truncate_owned_tables(session)
        await populate_registry(session, starting_state)

        for algorithm in (AlgorithmName.GREEDY, AlgorithmName.WEIGHTED):
            await reset_bed_state(session, starting_state)
            report = await run_contention_burst(session, cases, starting_state, algorithm=algorithm)
            out = _contention_report_to_dict(report)
            path = _RAW_DIR / f"r5_contention_{algorithm.value}.json"
            path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"wrote {path} (double_bookings={report.double_bookings})")

    await get_engine().dispose()


def compute_geographic_reachability() -> None:
    """For each case origin, which tertiary facilities lie within R(critical)=30 min
    (Haversine, the same formula/speed the live engine uses — verified against
    app/domain/travel/live.py + haversine.py, api_key="" always falls back to this path)."""
    cases = json.loads(_CASE_SET.read_text(encoding="utf-8"))
    facilities = json.loads(_STARTING_STATE.read_text(encoding="utf-8"))
    tertiary = [f for f in facilities if f["tier"] == "tertiary"]
    radius = RADIUS_MINUTES[Urgency.CRITICAL]

    origins: dict[str, dict] = {}
    rows = []
    for case in cases:
        key = f"{case['origin_lat']},{case['origin_lon']}"
        if key not in origins:
            origin = Coordinate(case["origin_lat"], case["origin_lon"])
            reachable = []
            for fac in tertiary:
                minutes = haversine_minutes(
                    origin, Coordinate(fac["latitude"], fac["longitude"])
                )
                reachable.append(
                    {
                        "facility_name": fac["name"],
                        "travel_time_minutes": round(minutes, 1),
                        "within_radius": minutes <= radius,
                    }
                )
            reachable.sort(key=lambda r: r["travel_time_minutes"])
            origins[key] = {
                "origin_lat": case["origin_lat"],
                "origin_lon": case["origin_lon"],
                "tertiary_facilities": reachable,
                "any_tertiary_within_radius": any(r["within_radius"] for r in reachable),
            }
        rows.append(
            {
                "case_id": case["case_id"],
                "origin_key": key,
                "note": case.get("_note"),
            }
        )

    out = {
        "radius_minutes_critical": radius,
        "tertiary_facility_count": len(tertiary),
        "origins": origins,
        "cases": rows,
        "origins_with_no_tertiary_within_radius": [
            {"origin_key": k, "note": next((r["note"] for r in rows if r["origin_key"] == k), None)}
            for k, v in origins.items()
            if not v["any_tertiary_within_radius"]
        ],
    }
    path = _RAW_DIR / "geographic_reachability.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    no_tertiary = len(out["origins_with_no_tertiary_within_radius"])
    print(f"wrote {path} ({no_tertiary} origins with no tertiary in radius)")


def _read_decisions() -> list[dict]:
    lines = (_STUDY_DIR / "decisions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def compute_tertiary_capacity_preservation() -> None:
    """Non-critical cases (urgent + standard) placed in a tertiary-tier ICU bed, primary run
    only, per strategy — not one of the six measures, read straight from decisions.jsonl."""
    decisions = _read_decisions()
    primary = [d for d in decisions if d["run"] == "primary"]

    result = {}
    for algorithm in (a.value for a in AlgorithmName):
        rows = [d for d in primary if d["algorithm"] == algorithm]
        non_critical = [d for d in rows if d["urgency"] != "critical"]
        non_critical_icu = [d for d in non_critical if d["required_bed_type"] == "icu"]
        placed_tertiary_icu = [
            d for d in non_critical_icu
            if d["status"] == "allocated"
            and d["selected_facility_id"] is not None
        ]
        # tier isn't on the decision line directly; re-derive from the candidate the case
        # actually selected (present in the same line's ranked candidate list).
        placed_tertiary_icu = [
            d for d in placed_tertiary_icu
            if any(
                c["facility_id"] == d["selected_facility_id"] and c["tier"] == "tertiary"
                for c in d["candidates"]
            )
        ]
        result[algorithm] = {
            "non_critical_icu_case_count": len(non_critical_icu),
            "placed_at_tertiary_icu": len(placed_tertiary_icu),
            "case_ids": [d["case_id"] for d in placed_tertiary_icu],
        }

    path = _RAW_DIR / "tertiary_capacity_preservation.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def compute_cross_strategy_diff() -> None:
    """Every case where the three primary-run strategies did not all pick the same outcome —
    same facility if all placed, or all escalated together."""
    decisions = _read_decisions()
    primary = [d for d in decisions if d["run"] == "primary"]
    by_case: dict[str, dict[str, dict]] = {}
    for d in primary:
        by_case.setdefault(d["case_id"], {})[d["algorithm"]] = d

    diffs = []
    for case_id, by_algo in sorted(by_case.items()):
        outcomes = {
            algo: (d["selected_facility_id"] or f"ESCALATED:{d['status']}")
            for algo, d in by_algo.items()
        }
        if len(set(outcomes.values())) > 1:
            detail = {}
            for algo, d in by_algo.items():
                if d["selected_facility_id"]:
                    scored = next(
                        c for c in d["candidates"] if c["facility_id"] == d["selected_facility_id"]
                    )
                    detail[algo] = {
                        "facility_id": d["selected_facility_id"],
                        "tier": scored["tier"],
                        "travel_time_min": scored["travel_time_min"],
                        "score": scored["score"],
                        "c_hat": scored["c_hat"],
                        "b_hat": scored["b_hat"],
                        "t_hat": scored["t_hat"],
                    }
                else:
                    detail[algo] = {"status": d["status"]}
            diffs.append(
                {
                    "case_id": case_id,
                    "urgency": by_algo[next(iter(by_algo))]["urgency"],
                    "required_bed_type": by_algo[next(iter(by_algo))]["required_bed_type"],
                    "by_strategy": detail,
                }
            )

    path = _RAW_DIR / "cross_strategy_diff.json"
    path.write_text(json.dumps(diffs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(diffs)} cases differ)")


def compute_escalations_full() -> None:
    """Every escalated case (primary run, all 3 strategies): full detail incl. fallbacks."""
    decisions = _read_decisions()
    primary = [d for d in decisions if d["run"] == "primary"]
    cases = {c["case_id"]: c for c in json.loads(_CASE_SET.read_text(encoding="utf-8"))}

    by_case: dict[str, dict[str, dict]] = {}
    for d in primary:
        by_case.setdefault(d["case_id"], {})[d["algorithm"]] = d

    result = []
    for case_id, by_algo in sorted(by_case.items()):
        escalated_by = {
            algo: d for algo, d in by_algo.items() if d["status"] == "escalated"
        }
        if not escalated_by:
            continue
        case = cases[case_id]
        result.append(
            {
                "case_id": case_id,
                "origin_lat": case["origin_lat"],
                "origin_lon": case["origin_lon"],
                "note": case.get("_note"),
                "urgency": case["urgency"],
                "required_bed_type": case["required_bed_type"],
                "escalated_by_strategies": sorted(escalated_by),
                "not_escalated_by_strategies": sorted(set(by_algo) - set(escalated_by)),
                "detail_by_strategy": {
                    algo: {
                        # H_f (the hard-filtered candidate set) — 0 on every one of these,
                        # since the primary run is sequential (never a race-exhausted
                        # escalation, which is the only path with a nonzero count here).
                        "candidates_evaluated": len(d["candidates"]),
                        "reservation_attempts": d["attempts"],
                        "selection_reason": d["selection_reason"],
                        "nearest_within_radius": d["nearest_within_radius"],
                        "nearest_available_outside_radius": d["nearest_available_outside_radius"],
                    }
                    for algo, d in escalated_by.items()
                },
            }
        )

    path = _RAW_DIR / "escalations_full.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(result)} escalated cases, union across strategies)")


def compute_travel_time_distribution() -> None:
    """Min/median/mean/max travel time to placement, and count exceeding 45 min, per primary-
    run strategy — a mean alone conceals a single pathological placement (evidence review)."""
    decisions = _read_decisions()
    primary = [d for d in decisions if d["run"] == "primary"]

    result = {}
    for algorithm in (a.value for a in AlgorithmName):
        placed = [d for d in primary if d["algorithm"] == algorithm and d["selected_facility_id"]]
        times = []
        for d in placed:
            c = next(c for c in d["candidates"] if c["facility_id"] == d["selected_facility_id"])
            times.append(c["travel_time_min"])
        times.sort()
        result[algorithm] = {
            "n_placed": len(times),
            "min": round(min(times), 1),
            "median": round(statistics.median(times), 1),
            "mean": round(statistics.mean(times), 1),
            "max": round(max(times), 1),
            "count_over_45_min": sum(1 for t in times if t > 45.0),
            "all_travel_times_sorted": [round(t, 1) for t in times],
        }

    path = _RAW_DIR / "travel_time_distribution.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def compute_standard_tier_facility_size_effect() -> None:
    """Every standard-urgency placement (primary run): chosen facility, its raw available-bed
    count, and its normalised b_hat — the numeric evidence for the bed-count-normalisation
    mechanism identified in the evidence review, stated directly rather than argued."""
    decisions = _read_decisions()
    primary = [d for d in decisions if d["run"] == "primary"]

    rows = []
    for d in primary:
        if d["urgency"] != "standard" or not d["selected_facility_id"]:
            continue
        c = next(c for c in d["candidates"] if c["facility_id"] == d["selected_facility_id"])
        rows.append(
            {
                "case_id": d["case_id"],
                "algorithm": d["algorithm"],
                "required_bed_type": d["required_bed_type"],
                "facility_id": d["selected_facility_id"],
                "tier": c["tier"],
                "available_beds": c["available_beds"],
                "b_hat": round(c["b_hat"], 3),
                "c_hat": round(c["c_hat"], 3),
                "travel_time_min": round(c["travel_time_min"], 1),
            }
        )
    rows.sort(key=lambda r: (r["case_id"], r["algorithm"]))

    path = _RAW_DIR / "standard_tier_facility_size_effect.json"
    path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(rows)} standard-tier placements)")


async def run_standard_tier_counterfactual() -> None:
    """R6 — POST-HOC DIAGNOSTIC, selected after observing the E2 contradiction, not an
    independent confirmation. Re-runs urgency_adaptive with ONLY the standard-tier weight
    vector changed to (w_t=0.40, w_b=0.35, w_c=0.25) — travel raised from 0.25, bed weight
    reduced from 0.50 — critical and urgent vectors left at their primary-run values. Tests
    whether the standard-tier shortfall is attributable to that one vector or to urgency
    conditioning generally.
    """
    cases = load_cases(str(_CASE_SET))
    starting_state = load_starting_state(str(_STARTING_STATE))
    defaults = StudyParameters.defaults()
    counterfactual_weights = dict(defaults.weights_urgency_adaptive)
    counterfactual_weights[Urgency.STANDARD] = WeightVector(w_t=0.40, w_b=0.35, w_c=0.25)
    counterfactual_params = StudyParameters(
        radius_minutes=defaults.radius_minutes,
        capability_matrix=defaults.capability_matrix,
        weights_weighted=defaults.weights_weighted,
        weights_urgency_adaptive=counterfactual_weights,
    )

    async with get_sessionmaker()() as session:
        await truncate_owned_tables(session)
        await populate_registry(session, starting_state)
        await reset_bed_state(session, starting_state)
        runs = await run_scenario_for_strategy(
            session, cases, AlgorithmName.URGENCY_ADAPTIVE, study_parameters=counterfactual_params
        )
    await get_engine().dispose()

    case_results = [
        CaseResult(
            case_id=r.case.case_id,
            urgency=r.case.urgency,
            allocated=r.selected_facility_id is not None,
            travel_time_minutes=r.selected_travel_time_minutes,
            capability_match=r.selected_capability_match,
            tier=r.selected_tier,
            attempts=r.attempts,
        )
        for r in runs
    ]
    by_tier = compute_measures_by_tier(case_results)
    standard = by_tier[Urgency.STANDARD]

    out = {
        "label": "POST-HOC DIAGNOSTIC — selected after observing the E2 contradiction, not an "
        "independent confirmation",
        "weight_vector_used": {
            "critical": defaults.weights_urgency_adaptive[Urgency.CRITICAL].model_dump(),
            "urgent": defaults.weights_urgency_adaptive[Urgency.URGENT].model_dump(),
            "standard_COUNTERFACTUAL": counterfactual_weights[Urgency.STANDARD].model_dump(),
            "standard_PRIMARY_RUN_FOR_COMPARISON": defaults.weights_urgency_adaptive[
                Urgency.STANDARD
            ].model_dump(),
        },
        "standard_tier_measures": {
            "case_count": standard.case_count,
            "placement_success": standard.placement_success,
            "escalation_rate": standard.escalation_rate,
            "mean_reservation_attempts_per_placed_case": (
                standard.mean_reservation_attempts_per_placed_case
            ),
            "mean_travel_time_minutes": standard.mean_travel_time_minutes,
            "mean_capability_match": standard.mean_capability_match,
        },
        "per_case": [
            {
                "case_id": r.case.case_id,
                "selected_facility_id": r.selected_facility_id,
                "tier": r.selected_tier.value if r.selected_tier else None,
                "travel_time_minutes": r.selected_travel_time_minutes,
                "capability_match": r.selected_capability_match,
            }
            for r in runs
        ],
    }
    path = _RAW_DIR / "r6_counterfactual_standard_weights.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def copy_canonical_artifacts_as_raw() -> None:
    """Attach the CLI's own four artifacts under analysis/raw/ too, per the brief's deliverable
    #2 ("raw JSON output for R1-R5") — measures.csv converted to JSON rows for convenience,
    the other three copied verbatim."""
    import shutil

    for name in ("decisions.jsonl", "manifest.json", "contention.json"):
        shutil.copy(_STUDY_DIR / name, _RAW_DIR / f"primary_robustness_{name}")

    with (_STUDY_DIR / "measures.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    (_RAW_DIR / "measures.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )
    print("copied canonical CLI artifacts into analysis/raw/")


async def _main() -> None:
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    await run_extra_contention_bursts()
    await run_standard_tier_counterfactual()
    compute_geographic_reachability()
    compute_tertiary_capacity_preservation()
    compute_cross_strategy_diff()
    compute_escalations_full()
    compute_travel_time_distribution()
    compute_standard_tier_facility_size_effect()
    copy_canonical_artifacts_as_raw()


if __name__ == "__main__":
    asyncio.run(_main())
