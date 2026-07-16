"""Simulation session lifecycle service (docs/04-api-spec.md §5, docs/07-simulation.md).

Wraps the engine with everything the API and the batch runner need: creating a session and
seeding its isolated bed state at the target occupancy, running a whole session (automatic
mode), stepping one event (interactive mode), and reading back per-event records + metrics.
A session's status is *derived* from how many events it has processed rather than stored, so
there is no status field to keep in sync (docs/02 §2.4 has none).

Bed reads/writes during a run go only to ``simulation_bed_state`` for the session; the live
``bed_count`` / ``facility`` tables are read-only (docs/02 §4). Sensitivity overrides
(``weight_config`` / ``radius_config`` / ``capability_config``) are *rejected* here rather
than silently ignored — the engine applies the ``parameters.py`` defaults in this phase, and
wiring per-session overrides into scoring is the evaluation/sensitivity pipeline's job
(Phase 5, RB-8). The main 270-run grid uses null overrides and is unaffected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.simulation_allocation_event import SimulationAllocationEvent
from app.db.models.simulation_bed_state import SimulationBedState
from app.db.models.simulation_session import SimulationSession
from app.domain.allocation.study_parameters import StudyParameters
from app.domain.travel.base import TravelTimeService
from app.parameters import AlgorithmName
from app.simulation.engine import ProcessedEvent, SimulationEngine
from app.simulation.events import generate_events
from app.simulation.metrics import EventMetricRow, RunMetrics, compute_run_metrics

SessionStatus = Literal["pending", "in_progress", "completed"]


class SimulationSessionNotFound(Exception):
    """Raised when a simulation session id does not exist (maps to HTTP 404)."""


class SimulationSessionStateError(Exception):
    """Raised on an invalid lifecycle transition, e.g. running a completed session (HTTP 409)."""


@dataclass(frozen=True)
class SessionState:
    """A session plus its derived progress (events processed, planned, and status)."""

    session: SimulationSession
    events_processed: int
    status: SessionStatus


@dataclass(frozen=True)
class SessionConfig:
    """Validated inputs for creating a session (docs/04 §5).

    The three ``*_config`` overrides are recorded on the session for audit (docs/02 §2.4). The
    API leaves them null (Phase 4); the sensitivity driver sets them to the variant it is
    running *and* passes the matching ``StudyParameters`` to the service.
    """

    algorithm_config: AlgorithmName
    occupancy_scenario: float
    events_planned: int
    random_seed: int
    weight_config: dict[str, Any] | None = None
    radius_config: dict[str, Any] | None = None
    capability_config: dict[str, Any] | None = None


class SimulationService:
    """Creates, runs, steps, and reports on simulation sessions (docs/04 §5)."""

    def __init__(
        self,
        session: AsyncSession,
        travel_service: TravelTimeService,
        study_parameters: StudyParameters | None = None,
    ) -> None:
        self._db = session
        self._travel = travel_service
        # None → parameters.py defaults; the sensitivity driver injects a variant's bundle.
        self._study_parameters = study_parameters

    # --- creation + seeding -------------------------------------------------

    async def create_session(self, config: SessionConfig) -> SimulationSession:
        """Create a session and seed its isolated bed state at the target occupancy (docs/07 §4)."""
        sim = SimulationSession(
            algorithm_config=config.algorithm_config,
            occupancy_scenario=Decimal(str(config.occupancy_scenario)),
            random_seed=config.random_seed,
            events_planned=config.events_planned,
            weight_config=config.weight_config,
            radius_config=config.radius_config,
            capability_config=config.capability_config,
        )
        self._db.add(sim)
        await self._db.flush()
        await self._seed_bed_state(sim, config.occupancy_scenario)
        await self._db.commit()
        await self._db.refresh(sim)
        return sim

    async def _seed_bed_state(self, sim: SimulationSession, occupancy: float) -> None:
        """Seed ``available = round(capacity·(1−occupancy))`` per facility/bed-type (docs/07 §4)."""
        bed_counts = (await self._db.scalars(select(BedCount))).all()
        for bed_count in bed_counts:
            available = round(bed_count.capacity * (1.0 - occupancy))
            self._db.add(
                SimulationBedState(
                    session_id=sim.id,
                    facility_id=bed_count.facility_id,
                    bed_type=bed_count.bed_type,
                    available=available,
                    capacity=bed_count.capacity,
                )
            )
        await self._db.flush()

    # --- status -------------------------------------------------------------

    async def get_state(self, session_id: uuid.UUID) -> SessionState:
        """Return the session and its derived progress, or raise if it does not exist."""
        sim = await self._db.get(SimulationSession, session_id)
        if sim is None:
            raise SimulationSessionNotFound(str(session_id))
        processed = await self._count_events(session_id)
        return SessionState(session=sim, events_processed=processed, status=_status(sim, processed))

    async def _count_events(self, session_id: uuid.UUID) -> int:
        """Count events already processed for the session (its position on the clock)."""
        total = await self._db.scalar(
            select(func.count())
            .select_from(SimulationAllocationEvent)
            .where(SimulationAllocationEvent.session_id == session_id)
        )
        return int(total or 0)

    # --- automatic mode -----------------------------------------------------

    async def run_session(self, session_id: uuid.UUID) -> RunMetrics:
        """Automatic mode: process every planned event and return the run metrics (docs/07 §5).

        Requires a fresh session (no events processed); re-running a session that already has
        events is a state conflict (HTTP 409) so a run is never silently doubled.
        """
        state = await self.get_state(session_id)
        if state.events_processed > 0:
            raise SimulationSessionStateError(
                f"session {session_id} already has {state.events_processed} processed events"
            )
        sim = state.session
        engine = SimulationEngine(sim, self._db, self._travel, self._study_parameters)
        for planned in generate_events(sim.random_seed, sim.events_planned):
            await engine.process_event(planned)
        await self._db.commit()
        return await self._metrics(session_id)

    # --- interactive mode ---------------------------------------------------

    async def step_session(self, session_id: uuid.UUID) -> ProcessedEvent:
        """Interactive mode: process the next event and return its full decision (docs/07 §5)."""
        state = await self.get_state(session_id)
        sim = state.session
        if state.events_processed >= sim.events_planned:
            raise SimulationSessionStateError(f"session {session_id} is already complete")
        planned = generate_events(sim.random_seed, sim.events_planned)[state.events_processed]
        engine = SimulationEngine(sim, self._db, self._travel, self._study_parameters)
        processed = await engine.process_event(planned)
        await self._db.commit()
        await self._db.refresh(processed.record)
        return processed

    # --- results ------------------------------------------------------------

    async def get_events(self, session_id: uuid.UUID) -> list[SimulationAllocationEvent]:
        """Return the session's per-event records in event order (raises if unknown session)."""
        await self.get_state(session_id)  # existence check (404 if unknown)
        records = await self._db.scalars(
            select(SimulationAllocationEvent)
            .where(SimulationAllocationEvent.session_id == session_id)
            .order_by(SimulationAllocationEvent.event_index)
        )
        return list(records.all())

    async def _metrics(self, session_id: uuid.UUID) -> RunMetrics:
        """Compute the run metrics from the session's persisted event records (docs/07 §8)."""
        records = await self.get_events(session_id)
        return compute_run_metrics([_to_metric_row(record) for record in records])

    async def get_results(
        self, session_id: uuid.UUID
    ) -> tuple[SessionState, list[SimulationAllocationEvent], RunMetrics]:
        """Return (session state, per-event records, aggregated metrics) for the results view."""
        state = await self.get_state(session_id)
        records = await self.get_events(session_id)
        metrics = compute_run_metrics([_to_metric_row(record) for record in records])
        return state, records, metrics


def _status(sim: SimulationSession, processed: int) -> SessionStatus:
    """Derive lifecycle status from progress: none → pending, all → completed, else running."""
    if processed == 0:
        return "pending"
    if processed >= sim.events_planned:
        return "completed"
    return "in_progress"


def _to_metric_row(record: SimulationAllocationEvent) -> EventMetricRow:
    """Project one persisted event onto the fields the metrics need (Decimal → float)."""
    return EventMetricRow(
        status=record.status,
        candidates_evaluated=record.candidates_evaluated,
        urgency=record.urgency,
        time_to_bed_placement_min=(
            float(record.time_to_bed_placement_min)
            if record.time_to_bed_placement_min is not None
            else None
        ),
        capability_match=(
            float(record.capability_match) if record.capability_match is not None else None
        ),
    )
