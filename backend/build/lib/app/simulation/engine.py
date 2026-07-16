"""The discrete-event simulation loop (docs/07-simulation.md §1-2, §6).

``SimulationEngine`` processes one planned event at a time against a session's isolated bed
state. It is a *client of the allocation engine*: it calls the same pure
``AllocationService.evaluate`` used by live dispatch, then layers the simulation-only bed
lifecycle on top — decrement on allocation, and release (increment) when a held bed's length
of stay elapses. Nothing here re-implements matching logic, so simulation and live decisions
are identical by construction.

Bed release is modelled from history rather than an in-memory queue: before an event at
virtual time ``t``, every earlier allocated event whose ``bed_release_virtual_min`` falls in
``(t_prev, t]`` returns its bed to the pool. Because that is a pure function of the persisted
event rows, ``/run`` (whole session in one call) and ``/step`` (one event per HTTP call)
share the exact same code path and produce identical state — the basis of reproducibility
(docs/07 §9) and of interactive stepping matching an automatic run.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.simulation_allocation_event import SimulationAllocationEvent
from app.db.models.simulation_session import SimulationSession
from app.domain.allocation.service import (
    AllocationOutcome,
    AllocationRequest,
    AllocationService,
)
from app.domain.allocation.study_parameters import StudyParameters
from app.domain.beds.simulation_source import SimulationDataSource
from app.domain.travel.base import TravelTimeService
from app.parameters import COORDINATION_OVERHEAD_MIN, Status
from app.simulation.events import PlannedEvent

# Lower bound sentinel below any possible arrival time, used when a session has no processed
# events yet (so the "releases due" window has no earlier boundary to exclude).
_NO_EARLIER_ARRIVAL = Decimal("-1")


@dataclass(frozen=True)
class ProcessedEvent:
    """A processed event: the persisted record plus the full decision (for the step trace)."""

    record: SimulationAllocationEvent
    outcome: AllocationOutcome


def _to_decimal(value: float) -> Decimal:
    """Convert a float to Decimal via its string form (exact, deterministic — matches audit)."""
    return Decimal(str(value))


class SimulationEngine:
    """Processes planned events for one session, owning the bed lifecycle (docs/07 §2)."""

    def __init__(
        self,
        session: SimulationSession,
        db_session: AsyncSession,
        travel_service: TravelTimeService,
        study_parameters: StudyParameters | None = None,
    ) -> None:
        self._session = session
        self._db = db_session
        self._bed_source = SimulationDataSource(db_session, session.id)
        self._allocation_service = AllocationService(db_session, travel_service, study_parameters)

    async def process_event(self, planned: PlannedEvent) -> ProcessedEvent:
        """Process one planned event: release due beds, allocate, and persist the record."""
        arrival = _to_decimal(planned.virtual_arrival_min)
        await self._apply_due_releases(arrival)

        outcome = await self._allocation_service.evaluate(
            AllocationRequest(
                patient_lat=planned.patient_lat,
                patient_lon=planned.patient_lon,
                required_bed_type=planned.required_bed_type,
                urgency=planned.urgency,
                simulation_session_id=self._session.id,
            )
        )

        record = await self._build_record(planned, arrival, outcome)
        self._db.add(record)
        await self._db.flush()
        return ProcessedEvent(record=record, outcome=outcome)

    async def _build_record(
        self, planned: PlannedEvent, arrival: Decimal, outcome: AllocationOutcome
    ) -> SimulationAllocationEvent:
        """Build the per-event row; on allocation also decrement the chosen bed (docs/02 §2.6)."""
        base = SimulationAllocationEvent(
            session_id=self._session.id,
            event_index=planned.event_index,
            virtual_arrival_min=arrival,
            urgency=planned.urgency,
            required_bed_type=planned.required_bed_type,
            patient_lat=_to_decimal(planned.patient_lat),
            patient_lon=_to_decimal(planned.patient_lon),
            candidates_evaluated=outcome.candidates_evaluated,
            status=outcome.status,
        )
        if outcome.status != Status.ALLOCATED or outcome.recommended is None:
            return base  # escalation: decision fields stay null (docs/02 §4)

        recommendation = outcome.recommended
        # Occupy the bed (docs/07 diagram: "allocate bed, decrement").
        await self._bed_source.allocate_bed(recommendation.facility_id, planned.required_bed_type)
        placement = COORDINATION_OVERHEAD_MIN + recommendation.travel_time_minutes
        base.recommended_facility_id = recommendation.facility_id
        base.travel_time_minutes = _to_decimal(recommendation.travel_time_minutes)
        base.time_to_bed_placement_min = _to_decimal(placement)
        base.capability_match = _to_decimal(recommendation.capability_match)
        base.los_minutes = _to_decimal(planned.los_minutes)
        base.bed_release_virtual_min = arrival + _to_decimal(planned.los_minutes)
        return base

    async def _apply_due_releases(self, arrival: Decimal) -> None:
        """Return to the pool every bed whose LOS elapsed in ``(t_prev, arrival]`` (docs/07 §2).

        ``t_prev`` is the last already-processed event's arrival, so each release is applied
        exactly once across the timeline — making the operation idempotent whether events are
        processed all at once (``/run``) or one per call (``/step``).
        """
        last_arrival = await self._db.scalar(
            select(func.max(SimulationAllocationEvent.virtual_arrival_min)).where(
                SimulationAllocationEvent.session_id == self._session.id
            )
        )
        lower = last_arrival if last_arrival is not None else _NO_EARLIER_ARRIVAL

        due = await self._db.execute(
            select(
                SimulationAllocationEvent.recommended_facility_id,
                SimulationAllocationEvent.required_bed_type,
                func.count().label("released"),
            )
            .where(
                SimulationAllocationEvent.session_id == self._session.id,
                SimulationAllocationEvent.status == Status.ALLOCATED,
                SimulationAllocationEvent.bed_release_virtual_min > lower,
                SimulationAllocationEvent.bed_release_virtual_min <= arrival,
            )
            .group_by(
                SimulationAllocationEvent.recommended_facility_id,
                SimulationAllocationEvent.required_bed_type,
            )
        )
        for facility_id, bed_type, released in due:
            if facility_id is None:
                continue  # facility row was deleted (SET NULL); nothing to release
            for _ in range(int(released)):
                await self._bed_source.release_bed(facility_id, bed_type)
