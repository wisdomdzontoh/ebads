"""Simulation endpoints (docs/04-api-spec.md §5, docs/07-simulation.md).

Exposes the session lifecycle: create (seeds isolated bed state), ``run`` (automatic mode —
process every event, return metrics), ``step`` (interactive mode — one event + full decision
trace), and the session/results reads. Travel times come from a precomputed distance matrix
(``MatrixTravelTimeService``) so runs never call live maps per event and stay reproducible
(docs/07 §3): the prebuilt study matrix if ``DISTANCE_MATRIX_PATH`` exists, otherwise an
in-memory Haversine matrix built from the registered facilities and cached per facility set.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.simulation import (
    RunMetricsRead,
    RunSummary,
    SimulationEventRead,
    SimulationResults,
    SimulationSessionCreate,
    SimulationSessionRead,
    StepCandidate,
    StepTrace,
)
from app.config import get_settings
from app.db.models.facility import Facility
from app.db.models.user_account import UserAccount
from app.db.session import get_session
from app.domain.allocation.scoring import rank_by_score
from app.domain.travel.base import TravelTimeService
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import PermissionAction
from app.security.dependencies import require_permission
from app.simulation.distance_matrix import (
    MatrixTravelTimeService,
    build_distance_matrix,
    load_distance_matrix,
)
from app.simulation.engine import ProcessedEvent
from app.simulation.metrics import RunMetrics
from app.simulation.service import (
    SessionConfig,
    SessionState,
    SimulationService,
    SimulationSessionNotFound,
    SimulationSessionStateError,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
# [IMPL] Research/dev tool, not a PRD-described role capability; gated to
# system_administrator as a minimal retrofit ahead of Increment 5's replacement
# (docs/07-scenario-testing.md) — see the migration's permission-seed comment.
RunnerDep = Annotated[
    UserAccount, Depends(require_permission("simulation", PermissionAction.WRITE))
]
ViewerDep = Annotated[
    UserAccount, Depends(require_permission("simulation", PermissionAction.READ))
]

# Cache built travel services so a 100-event run does not rebuild the matrix each request.
# Keyed so a rebuilt matrix file (new mtime) or a different facility set busts the entry.
_travel_cache: dict[str, MatrixTravelTimeService] = {}


async def get_simulation_travel_service(session: SessionDep) -> TravelTimeService:
    """Provide the matrix-backed travel service for the simulation path (docs/07 §3).

    Uses the prebuilt study matrix when configured and present; otherwise builds a Haversine
    matrix (never live maps — that would break per-event reproducibility) over the registered
    facilities. Overridable in tests.
    """
    matrix_path = Path(get_settings().distance_matrix_path)
    if matrix_path.exists():
        key = f"file::{matrix_path.resolve()}::{matrix_path.stat().st_mtime_ns}"
        if key not in _travel_cache:
            _travel_cache[key] = MatrixTravelTimeService(load_distance_matrix(matrix_path))
        return _travel_cache[key]

    facilities = (await session.scalars(select(Facility).order_by(Facility.name))).all()
    triples = [(str(f.id), float(f.latitude), float(f.longitude)) for f in facilities]
    key = "haversine::" + ";".join(f"{lat:.6f},{lon:.6f}" for _, lat, lon in triples)
    if key not in _travel_cache:
        # Empty api key forces the Haversine estimate for every cell (docs/09 §7).
        matrix = await build_distance_matrix(triples, LiveTravelTimeService(""))
        _travel_cache[key] = MatrixTravelTimeService(matrix)
    return _travel_cache[key]


def _simulation_service(
    session: SessionDep,
    travel: Annotated[TravelTimeService, Depends(get_simulation_travel_service)],
) -> SimulationService:
    return SimulationService(session, travel)


ServiceDep = Annotated[SimulationService, Depends(_simulation_service)]


def _session_read(state: SessionState) -> SimulationSessionRead:
    """Map the domain session state onto the API read model (docs/04 §5)."""
    sim = state.session
    return SimulationSessionRead(
        id=sim.id,
        algorithm_config=sim.algorithm_config,
        occupancy_scenario=float(sim.occupancy_scenario),
        events_planned=sim.events_planned,
        random_seed=sim.random_seed,
        created_at=sim.created_at,
        status=state.status,
        events_processed=state.events_processed,
    )


def _metrics_read(metrics: RunMetrics) -> RunMetricsRead:
    """Map the domain run metrics onto the API read model (docs/07 §8)."""
    return RunMetricsRead(
        atbp=metrics.atbp,
        frr=metrics.frr,
        mcee=metrics.mcee,
        cm=metrics.cm,
        cm_critical=metrics.cm_critical,
        events_total=metrics.events_total,
        events_allocated=metrics.events_allocated,
        events_escalated=metrics.events_escalated,
    )


def _step_trace(processed: ProcessedEvent) -> StepTrace:
    """Build the interactive decision trace from a processed event (docs/04 §5).

    Candidates are returned ranked by ascending score (the engine's own deterministic order:
    score → travel time → facility id, the same tie-break as selection). Ranking here — where
    the scores were computed — lets the mobile client render ranks without doing any ranking
    itself (docs/05 §8): the first candidate is the selected one.
    """
    outcome = processed.outcome
    ranked = rank_by_score(outcome.scored)
    candidates = [
        StepCandidate(
            facility_id=uuid.UUID(scored.candidate.facility_id),
            travel_time_minutes=scored.candidate.travel_time_min,
            available_beds=scored.candidate.available_beds,
            t_hat=scored.t_hat,
            b_hat=scored.b_hat,
            c_hat=scored.c_hat,
            score=scored.score,
        )
        for scored in ranked
    ]
    return StepTrace(
        event_index=processed.record.event_index,
        candidates=candidates,
        selected_facility_id=processed.record.recommended_facility_id,
        algorithm_used=outcome.algorithm_used,
        weight_vector=outcome.weight_vector,
        status=outcome.status,
    )


@router.post("/sessions", response_model=SimulationSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SimulationSessionCreate, service: ServiceDep, _actor: RunnerDep
) -> SimulationSessionRead:
    """Create a session and seed its isolated bed state at the target occupancy (docs/04 §5)."""
    sim = await service.create_session(
        SessionConfig(
            algorithm_config=payload.algorithm_config,
            occupancy_scenario=payload.occupancy_scenario,
            events_planned=payload.events_planned,
            random_seed=payload.random_seed,
        )
    )
    return _session_read(await service.get_state(sim.id))


@router.post("/sessions/{session_id}/run", response_model=RunSummary)
async def run_session(session_id: uuid.UUID, service: ServiceDep, _actor: RunnerDep) -> RunSummary:
    """Automatic mode: process all planned events and return the run metrics (docs/04 §5)."""
    try:
        metrics = await service.run_session(session_id)
        state = await service.get_state(session_id)
    except SimulationSessionNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation session not found") from exc
    except SimulationSessionStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return RunSummary(
        session_id=session_id,
        events_processed=state.events_processed,
        status=state.status,
        metrics=_metrics_read(metrics),
    )


@router.post("/sessions/{session_id}/step", response_model=StepTrace)
async def step_session(session_id: uuid.UUID, service: ServiceDep, _actor: RunnerDep) -> StepTrace:
    """Interactive mode: process one event and return its full decision trace (docs/04 §5)."""
    try:
        processed = await service.step_session(session_id)
    except SimulationSessionNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation session not found") from exc
    except SimulationSessionStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _step_trace(processed)


@router.get("/sessions/{session_id}", response_model=SimulationSessionRead)
async def get_session_endpoint(
    session_id: uuid.UUID, service: ServiceDep, _actor: ViewerDep
) -> SimulationSessionRead:
    """Return a session's configuration and derived progress (docs/04 §5)."""
    try:
        state = await service.get_state(session_id)
    except SimulationSessionNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation session not found") from exc
    return _session_read(state)


@router.get("/sessions/{session_id}/results", response_model=SimulationResults)
async def get_results(
    session_id: uuid.UUID, service: ServiceDep, _actor: ViewerDep
) -> SimulationResults:
    """Return per-event records + aggregated metrics for a session (docs/04 §5)."""
    try:
        state, records, metrics = await service.get_results(session_id)
    except SimulationSessionNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "simulation session not found") from exc
    return SimulationResults(
        session=_session_read(state),
        metrics=_metrics_read(metrics),
        events=[SimulationEventRead.model_validate(record) for record in records],
    )
