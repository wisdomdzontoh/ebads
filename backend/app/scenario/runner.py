"""Scenario replay: populate the registry, run one case set per strategy under depletion,
and the contention-mode burst (docs/07-scenario-testing.md §2, §5, §7, FR23, FR8/FR9).

``run_all_strategies`` reproduces docs/07 §7's pseudocode exactly, over the *live* allocation
engine (``domain/allocation/service.py``) — same hard filter, same normalisation, same
scoring, same reservation, for every strategy. Nothing here re-implements matching.

Facility ids are derived from the facility name with ``uuid.uuid5`` — a deterministic hash of
that name, the same value on every run — rather than the model's default ``uuid.uuid4``,
which generates a different value each time. The scoring tie-break's final key is
``facility_id`` (``domain/allocation/scoring.py``'s ``_sort_key``), so a facility with a
different id on every run could flip a genuine tie's outcome between runs and break the
byte-identical-output guarantee this package exists to provide.

Run this against a dedicated/scratch database: ``main()`` truncates every table it populates
or writes to before loading the fixtures (facility, bed_count, and the allocation/
reservation/decision-log/notification history a live-path ``allocate()`` call writes) so a
run starts from exactly the case set and starting state on disk, never from whatever a
previous invocation left.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.facility import Facility
from app.db.session import get_engine, get_sessionmaker
from app.domain.allocation.candidate import ScoredCandidate
from app.domain.allocation.scoring import rank_by_score
from app.domain.allocation.service import (
    AllocationOutcome,
    AllocationRequest,
    AllocationService,
    FacilityBrief,
)
from app.domain.allocation.study_parameters import StudyParameters
from app.domain.beds.manual_adapter import ManualAdapter
from app.domain.notify.log_gateway import LogGateway
from app.domain.reservation.manager import reserve_from_ranking
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import ROBUSTNESS_CHECK_WEIGHTS, AlgorithmName, BedType, Status, Tier
from app.scenario.case_set import Case, load_cases

# A fixed namespace for the deterministic facility-id derivation described in the module
# docstring — any stable UUID works here; what matters is that it never changes between runs.
_FACILITY_NAMESPACE = uuid.UUID("2f5f9f2e-7b1a-4b7a-9e7a-1f6a2b6f9c11")

STRATEGIES: tuple[AlgorithmName, ...] = (
    AlgorithmName.GREEDY,
    AlgorithmName.WEIGHTED,
    AlgorithmName.URGENCY_ADAPTIVE,
)

# Tables a scenario run populates or writes to, in FK-safe order for TRUNCATE ... CASCADE.
_OWNED_TABLES = (
    "notification",
    "decision_log",
    "reservation",
    "allocation",
    "emergency_request",
    "bed_count",
    "facility",
)


@dataclass(frozen=True)
class BedCountState:
    bed_type: BedType
    available: int
    capacity: int


@dataclass(frozen=True)
class FacilityState:
    """One facility's static attributes plus its starting bed state (docs/07 §4)."""

    name: str
    latitude: float
    longitude: float
    tier: Tier
    supported_bed_types: list[BedType]
    contact_phone: str
    bed_counts: list[BedCountState]


def load_starting_state(path: str) -> list[FacilityState]:
    """Load the starting bed state from ``path`` — a JSON snapshot, loaded not generated."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    states = []
    for entry in raw:
        states.append(
            FacilityState(
                name=entry["name"],
                latitude=float(entry["latitude"]),
                longitude=float(entry["longitude"]),
                tier=Tier(entry["tier"]),
                supported_bed_types=[BedType(b) for b in entry["supported_bed_types"]],
                contact_phone=entry["contact_phone"],
                bed_counts=[
                    BedCountState(
                        bed_type=BedType(bc["bed_type"]),
                        available=int(bc["available"]),
                        capacity=int(bc["capacity"]),
                    )
                    for bc in entry["bed_counts"]
                ],
            )
        )
    return states


def _facility_id_for(name: str) -> uuid.UUID:
    """Deterministically derive a facility id from its name — see the module docstring."""
    return uuid.uuid5(_FACILITY_NAMESPACE, name)


async def truncate_owned_tables(session: AsyncSession) -> None:
    """Clear every table a scenario run populates or writes to, so a run starts clean.

    Only ever called by the CLI (``main()``), never by ``run_all_strategies`` — a caller that
    already owns a shared session (an integration test's fixture, say) manages its own
    isolation and must not have its data wiped out from under it by this package.
    """
    await session.execute(text(f"TRUNCATE TABLE {', '.join(_OWNED_TABLES)} CASCADE"))
    await session.commit()


async def populate_registry(session: AsyncSession, states: list[FacilityState]) -> None:
    """Upsert the facility registry and its starting bed counts, by name (docs/07 §2).

    Idempotent and safe to call at the start of every run: an existing row (same
    deterministic id) is updated in place rather than duplicated.
    """
    for state in states:
        facility_id = _facility_id_for(state.name)
        facility = await session.get(Facility, facility_id)
        if facility is None:
            facility = Facility(id=facility_id, name=state.name)
            session.add(facility)
        facility.latitude = Decimal(str(state.latitude))
        facility.longitude = Decimal(str(state.longitude))
        facility.tier = state.tier
        facility.supported_bed_types = state.supported_bed_types
        facility.contact_phone = state.contact_phone
        facility.active_data_source = None
        await session.flush()

        for bed_count in state.bed_counts:
            existing = await session.scalar(
                select(BedCount).where(
                    BedCount.facility_id == facility_id, BedCount.bed_type == bed_count.bed_type
                )
            )
            if existing is None:
                session.add(
                    BedCount(
                        facility_id=facility_id,
                        bed_type=bed_count.bed_type,
                        available=bed_count.available,
                        capacity=bed_count.capacity,
                        version=0,
                    )
                )
            else:
                existing.available = bed_count.available
                existing.capacity = bed_count.capacity
                existing.version = 0
    await session.commit()


async def reset_bed_state(session: AsyncSession, states: list[FacilityState]) -> None:
    """Reset every registered facility's bed counts to the starting snapshot (docs/07 §5, §7).

    Facility rows themselves are untouched — only availability/version reset, so every
    strategy starts from an identical starting state without re-inserting the registry.
    """
    for state in states:
        facility_id = _facility_id_for(state.name)
        for bed_count in state.bed_counts:
            await session.execute(
                update(BedCount)
                .where(
                    BedCount.facility_id == facility_id, BedCount.bed_type == bed_count.bed_type
                )
                .values(available=bed_count.available, version=0)
            )
    await session.commit()


@dataclass(frozen=True)
class CandidateTrace:
    """One ranked, scored candidate — the raw material of docs/07 §7's decision trace
    ("candidates, t̂/b̂/ĉ, scores, selection")."""

    facility_id: str
    tier: Tier
    travel_time_min: float
    available_beds: int
    t_hat: float
    b_hat: float
    c_hat: float
    score: float


@dataclass(frozen=True)
class FallbackTrace:
    """One escalation fallback facility (docs/04 §4's ``FacilityBrief``, docs/01 §7 FR11):
    either the nearest facility still within the urgency radius (but with no available bed
    of the requested type), or the nearest facility with an available bed outside it."""

    facility_id: str
    facility_name: str
    travel_time_minutes: float
    available_beds: int


@dataclass(frozen=True)
class CaseRun:
    """Everything one case's replay produced: the raw material for both the thesis Table
    3.10 measures (docs/07 §6) and the full per-case decision trace (docs/07 §7).
    """

    case: Case
    status: Status
    algorithm_used: AlgorithmName
    selection_reason: str
    candidates: list[CandidateTrace]  # ranked order; empty iff H_e was empty (docs/03 §1)
    selected_facility_id: str | None
    selected_tier: Tier | None
    selected_travel_time_minutes: float | None
    selected_capability_match: float | None
    attempts: int
    # Populated only on an escalation (docs/04 §4) — the two named fallbacks FR11 reports
    # to the dispatcher. Both None on a placed case, and both None on an escalation where
    # no facility of any kind supports the requested bed type at all.
    nearest_within_radius: FallbackTrace | None = None
    nearest_available_outside_radius: FallbackTrace | None = None


def _to_fallback_trace(brief: FacilityBrief | None) -> FallbackTrace | None:
    if brief is None:
        return None
    return FallbackTrace(
        facility_id=str(brief.facility_id),
        facility_name=brief.name,
        travel_time_minutes=brief.travel_time_minutes,
        available_beds=brief.available_beds,
    )


def _to_case_run(case: Case, outcome: AllocationOutcome) -> CaseRun:
    candidates = [
        CandidateTrace(
            facility_id=sc.candidate.facility_id,
            tier=sc.candidate.tier,
            travel_time_min=sc.candidate.travel_time_min,
            available_beds=sc.candidate.available_beds,
            t_hat=sc.t_hat,
            b_hat=sc.b_hat,
            c_hat=sc.c_hat,
            score=sc.score,
        )
        for sc in rank_by_score(outcome.scored)
    ]
    recommended = outcome.recommended
    allocated = outcome.status == Status.ALLOCATED and recommended is not None
    return CaseRun(
        case=case,
        status=outcome.status,
        algorithm_used=outcome.algorithm_used,
        selection_reason=outcome.selection_reason,
        candidates=candidates,
        selected_facility_id=str(recommended.facility_id) if allocated and recommended else None,
        selected_tier=recommended.tier if allocated and recommended else None,
        selected_travel_time_minutes=(
            recommended.travel_time_minutes if allocated and recommended else None
        ),
        selected_capability_match=(
            recommended.capability_match if allocated and recommended else None
        ),
        attempts=outcome.attempts,
        nearest_within_radius=_to_fallback_trace(outcome.nearest_within_radius),
        nearest_available_outside_radius=_to_fallback_trace(
            outcome.nearest_available_outside_radius
        ),
    )


async def run_scenario_for_strategy(
    session: AsyncSession,
    cases: list[Case],
    algorithm: AlgorithmName,
    study_parameters: StudyParameters | None = None,
) -> list[CaseRun]:
    """Replay ``cases`` in file order against one strategy, depleting bed state as it goes.

    Reuses the live allocation engine unchanged (docs/07 §2): each case goes through
    ``AllocationService.allocate`` — hard filter, scoring, and the FR8/FR9 reservation
    compare-and-set loop — with ``forced_algorithm`` pinning which strategy scores it.
    """
    service = AllocationService(
        session,
        travel_service=LiveTravelTimeService(api_key=""),  # Haversine only — deterministic
        study_parameters=study_parameters,
        sms_gateway=LogGateway(),
    )
    results: list[CaseRun] = []
    for case in cases:
        outcome = await service.allocate(
            AllocationRequest(
                patient_lat=case.origin_lat,
                patient_lon=case.origin_lon,
                required_bed_type=case.required_bed_type,
                urgency=case.urgency,
                forced_algorithm=algorithm,
            )
        )
        results.append(_to_case_run(case, outcome))
    return results


async def run_all_strategies(
    session: AsyncSession,
    cases: list[Case],
    starting_state: list[FacilityState],
    strategies: tuple[AlgorithmName, ...] = STRATEGIES,
    study_parameters: StudyParameters | None = None,
) -> dict[AlgorithmName, list[CaseRun]]:
    """Run ``cases`` against every strategy in ``strategies``, each from an identical starting
    state (docs/07 §7). Populates the registry once; resets bed state before each.
    """
    await populate_registry(session, starting_state)
    results: dict[AlgorithmName, list[CaseRun]] = {}
    for algorithm in strategies:
        await reset_bed_state(session, starting_state)
        results[algorithm] = await run_scenario_for_strategy(
            session, cases, algorithm, study_parameters
        )
    return results


# The robustness check only ever varies a weight vector, so it is meaningless for Greedy,
# which carries none (domain/allocation/algorithms/greedy.py) — re-running it would just
# reproduce its default-run result under a different label.
ROBUSTNESS_STRATEGIES: tuple[AlgorithmName, ...] = (
    AlgorithmName.WEIGHTED,
    AlgorithmName.URGENCY_ADAPTIVE,
)


def _robustness_parameters() -> StudyParameters:
    """One alternative weight table (thesis §3.8.4, docs/09 §12) — not a family (docs/07 §8)."""
    defaults = StudyParameters.defaults()
    return StudyParameters(
        radius_minutes=defaults.radius_minutes,
        capability_matrix=defaults.capability_matrix,
        weights_weighted=defaults.weights_weighted,
        weights_urgency_adaptive=ROBUSTNESS_CHECK_WEIGHTS,
    )


async def run_robustness_check(
    session: AsyncSession, cases: list[Case], starting_state: list[FacilityState]
) -> dict[AlgorithmName, list[CaseRun]]:
    """Re-run the complete case set under the §3.8.4 alternative weight table (docs/07 §8).

    Purpose is confined to establishing whether a difference between fixed-weight and
    urgency-adaptive survives a change in the degree of urgency conditioning — not a
    sensitivity sweep, one re-run under one variant.
    """
    return await run_all_strategies(
        session,
        cases,
        starting_state,
        strategies=ROBUSTNESS_STRATEGIES,
        study_parameters=_robustness_parameters(),
    )


@dataclass(frozen=True)
class ContentionCaseResult:
    """One burst case's outcome under contention mode (FR8/FR9)."""

    case_id: str
    reserved_facility_name: str | None
    attempts: int


@dataclass(frozen=True)
class ContentionReport:
    """Contention-mode summary: a burst scored against one shared snapshot, then reserved
    in sequence, so later cases in the burst may find their top-ranked candidate already
    taken by an earlier one — exercising the FR9 fall-through deliberately (docs/01 §7).
    """

    algorithm: AlgorithmName
    case_results: list[ContentionCaseResult]
    double_bookings: int


async def run_contention_burst(
    session: AsyncSession,
    cases: list[Case],
    starting_state: list[FacilityState],
    algorithm: AlgorithmName = AlgorithmName.URGENCY_ADAPTIVE,
) -> ContentionReport:
    """Score every case in ``cases`` against one unchanged starting snapshot (as if every
    dispatcher queried at the same instant, before anyone committed), then attempt
    reservations one case at a time in file order (docs/01 §7, FR8/FR9).

    Uses ``AllocationService.evaluate`` (no reservation, no persistence) for the batch
    scoring phase and ``reserve_from_ranking`` — the same fall-through loop ``allocate``
    itself calls — for the sequential reservation phase, rather than ``allocate`` end to
    end, precisely so every case's scoring reads the identical starting state.
    """
    await populate_registry(session, starting_state)
    await reset_bed_state(session, starting_state)

    service = AllocationService(
        session,
        travel_service=LiveTravelTimeService(api_key=""),
        sms_gateway=LogGateway(),
    )
    bed_source = ManualAdapter(session)

    scored_by_case: list[tuple[Case, list[ScoredCandidate]]] = []
    for case in cases:
        outcome = await service.evaluate(
            AllocationRequest(
                patient_lat=case.origin_lat,
                patient_lon=case.origin_lon,
                required_bed_type=case.required_bed_type,
                urgency=case.urgency,
                forced_algorithm=algorithm,
            )
        )
        scored_by_case.append((case, outcome.scored))

    facility_names: dict[str, str] = {
        str(_facility_id_for(state.name)): state.name for state in starting_state
    }
    # Starting availability per (facility_id, bed_type) — reserving the same key more than
    # once across the burst is expected whenever a facility has more than one bed; what must
    # never happen is the number of successful reservations at a key exceeding how many beds
    # it actually started with (that would mean the CAS oversold the pool).
    starting_available: dict[tuple[str, BedType], int] = {
        (str(_facility_id_for(state.name)), bed_count.bed_type): bed_count.available
        for state in starting_state
        for bed_count in state.bed_counts
    }
    reservations_by_key: dict[tuple[str, BedType], int] = {}

    case_results: list[ContentionCaseResult] = []
    for case, scored in scored_by_case:
        if not scored:
            case_results.append(
                ContentionCaseResult(case_id=case.case_id, reserved_facility_name=None, attempts=0)
            )
            continue
        result = await reserve_from_ranking(bed_source, scored, case.required_bed_type)
        reserved_name = None
        if result.reserved is not None:
            facility_id = result.reserved.candidate.facility_id
            key = (facility_id, case.required_bed_type)
            reservations_by_key[key] = reservations_by_key.get(key, 0) + 1
            reserved_name = facility_names.get(facility_id, facility_id)
        case_results.append(
            ContentionCaseResult(
                case_id=case.case_id, reserved_facility_name=reserved_name, attempts=result.attempts
            )
        )
    await session.commit()

    double_bookings = sum(
        max(0, count - starting_available.get(key, 0)) for key, count in reservations_by_key.items()
    )
    return ContentionReport(
        algorithm=algorithm, case_results=case_results, double_bookings=double_bookings
    )


# backend/app/scenario/runner.py -> backend/ -> repo root -> artifacts/ (docs/07 §7's
# "Outputs under artifacts/scenario/<study_id>/" — the same top-level artifacts/ directory
# the design-system materials already live under, not a backend-local one).
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a fixed scenario case set against every matching strategy "
        "under depleting bed state (FR23, docs/07-scenario-testing.md)."
    )
    parser.add_argument("--case-set", required=True, help="Path to the case-set JSON file.")
    parser.add_argument(
        "--starting-state",
        help="Path to the starting bed-state JSON file. Defaults to "
        "<case-set-directory>/<case-set-stem>_starting_state.json.",
    )
    parser.add_argument(
        "--study-id",
        required=True,
        help="Identifies this run's output directory: artifacts/scenario/<study-id>/ "
        "(docs/07-scenario-testing.md §7).",
    )
    return parser.parse_args(argv)


def _default_starting_state_path(case_set_path: str) -> str:
    """``<dir>/<stem>_starting_state.json`` alongside the case set — see ``data/case_sets/``."""
    p = Path(case_set_path)
    return str(p.with_name(f"{p.stem}_starting_state.json"))


async def _main_async(argv: list[str] | None = None) -> None:
    from app.scenario.report import write_report

    args = _parse_args(argv)
    starting_state_path = args.starting_state or _default_starting_state_path(args.case_set)

    cases = load_cases(args.case_set)
    starting_state = load_starting_state(starting_state_path)
    output_dir = _REPO_ROOT / "artifacts" / "scenario" / args.study_id

    async with get_sessionmaker()() as session:
        await truncate_owned_tables(session)
        await write_report(
            session, cases, starting_state, args.case_set, starting_state_path, output_dir
        )
    await get_engine().dispose()
    print(f"wrote {output_dir}")


def main(argv: list[str] | None = None) -> None:
    asyncio.run(_main_async(argv))


if __name__ == "__main__":
    main()
