"""``SimulationDataSource`` — the built Bridge implementation (docs/01 §3.2, status: built).

Reads and writes a single ``SimulationSession``'s isolated bed state. It scopes every query
to its ``simulation_session_id`` and only ever touches ``simulation_bed_state`` — never the
live ``bed_count`` or ``facility`` tables (docs/02 §4 invariant). On allocation it decrements
the session's available count (docs/12 §4).

Mutations are flushed, not committed: the caller (the simulation engine, Phase 4) owns the
transaction boundary so a whole event can be processed atomically.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.simulation_bed_state import SimulationBedState
from app.domain.beds.base import BedDataSource, BedUnavailableError
from app.parameters import BedType


class SimulationDataSource(BedDataSource):
    """Bed availability backed by one simulation session's isolated state (docs/01 §3.2)."""

    def __init__(self, session: AsyncSession, simulation_session_id: uuid.UUID) -> None:
        self._session = session
        self._simulation_session_id = simulation_session_id

    def _bed_state_query(
        self, facility_id: uuid.UUID, bed_type: BedType
    ) -> Select[tuple[SimulationBedState]]:
        """Build the query selecting this session's state row for a facility + bed type."""
        return select(SimulationBedState).where(
            SimulationBedState.session_id == self._simulation_session_id,
            SimulationBedState.facility_id == facility_id,
            SimulationBedState.bed_type == bed_type,
        )

    async def get_available_beds(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        """Return this session's available beds; 0 if the session does not track that row."""
        available = await self._session.scalar(
            select(SimulationBedState.available).where(
                SimulationBedState.session_id == self._simulation_session_id,
                SimulationBedState.facility_id == facility_id,
                SimulationBedState.bed_type == bed_type,
            )
        )
        return int(available) if available is not None else 0

    async def allocate_bed(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        """Decrement this session's available count by one and return the remainder.

        Raises ``BedUnavailableError`` if no bed is free — the engine only allocates to
        facilities that passed the hard filter (beds >= 1), so this guards an invariant
        rather than expecting to trip in normal flow.
        """
        bed_state = await self._session.scalar(self._bed_state_query(facility_id, bed_type))
        if bed_state is None or bed_state.available <= 0:
            raise BedUnavailableError(
                f"no available {bed_type} bed at facility {facility_id} "
                f"in session {self._simulation_session_id}"
            )
        bed_state.available -= 1
        await self._session.flush()
        return bed_state.available

    async def release_bed(self, facility_id: uuid.UUID, bed_type: BedType) -> int:
        """Return one bed to this session's pool (increment available) and return the new count.

        The other half of the simulation bed lifecycle (docs/07 §2): a patient allocated at
        time ``t`` holds the bed until ``t + los``, at which point the engine releases it.
        Availability is capped at ``capacity`` — a bed is only ever released after it was
        allocated, so this guards the ``available <= capacity`` invariant rather than
        expecting to trip. Raises ``BedUnavailableError`` if the row is not tracked, which
        would signal an engine bug (releasing a bed the session never seeded).
        """
        bed_state = await self._session.scalar(self._bed_state_query(facility_id, bed_type))
        if bed_state is None:
            raise BedUnavailableError(
                f"cannot release untracked {bed_type} bed at facility {facility_id} "
                f"in session {self._simulation_session_id}"
            )
        if bed_state.available < bed_state.capacity:
            bed_state.available += 1
        await self._session.flush()
        return bed_state.available
