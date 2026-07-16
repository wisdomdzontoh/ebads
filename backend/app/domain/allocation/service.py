"""Emergency Request & Allocation Service (docs/01 §3.3, docs/03, docs/04 §4).

Orchestrates one allocation: resolve the algorithm + bed source, build candidates (travel
time + available beds) over the facilities that support the requested bed type, run the
shared scoring pipeline, and return a recommendation or a structured escalation. ``allocate``
additionally persists the audit record (docs/02 §2.3).

This service is read-only with respect to bed state — it never decrements a bed. In
simulation, the engine (Phase 4) performs the decrement and LOS scheduling; live dispatch
has no cross-patient bed contention (PRD §5). ``evaluate`` therefore has no side effects on
availability and is reused unchanged by the simulation engine.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.simulation_session import SimulationSession
from app.domain.allocation.candidate import Candidate, ScoredCandidate
from app.domain.allocation.hard_filter import escalation_fallbacks
from app.domain.allocation.scoring import ScoringResult, run_scoring
from app.domain.allocation.selector import select_algorithm
from app.domain.allocation.study_parameters import StudyParameters
from app.domain.beds.base import BedDataSource
from app.domain.beds.local_source import LocalBedCountSource
from app.domain.beds.simulation_source import SimulationDataSource
from app.domain.travel.base import Coordinate, TravelTimeService
from app.parameters import (
    DEFAULT_URGENCY_WHEN_MISSING,
    AlgorithmName,
    BedType,
    Status,
    Tier,
    Urgency,
    WeightVector,
)


class SimulationSessionNotFoundError(Exception):
    """Raised when an allocation references a simulation session id that does not exist."""


@dataclass(frozen=True)
class AllocationRequest:
    """Parsed inputs for one allocation (docs/04 §4)."""

    patient_lat: float
    patient_lon: float
    required_bed_type: BedType
    urgency: Urgency | None = None
    simulation_session_id: uuid.UUID | None = None


@dataclass(frozen=True)
class FacilityRecommendation:
    """The chosen facility, with everything the response needs (docs/04 §4)."""

    facility_id: uuid.UUID
    name: str
    tier: Tier
    available_beds: int
    travel_time_minutes: float
    is_estimated_travel_time: bool
    latitude: float
    longitude: float
    contact_phone: str
    capability_match: float


@dataclass(frozen=True)
class FacilityBrief:
    """A minimal facility reference for an escalation fallback (docs/04 §4)."""

    facility_id: uuid.UUID
    name: str
    travel_time_minutes: float
    available_beds: int


@dataclass
class AllocationOutcome:
    """The decision for one request: a recommendation or an escalation (docs/04 §4)."""

    status: Status
    algorithm_used: AlgorithmName
    candidates_evaluated: int
    selection_reason: str
    weight_vector: WeightVector | None = None
    recommended: FacilityRecommendation | None = None
    nearest_within_radius: FacilityBrief | None = None
    nearest_available_outside_radius: FacilityBrief | None = None
    # Full scored set, for the simulation step trace (Phase 4). Empty on escalation.
    scored: list[ScoredCandidate] = field(default_factory=list)
    # Set after the audit record is persisted by ``allocate``.
    id: uuid.UUID | None = None


_BED_LABELS: Mapping[BedType, str] = {
    BedType.GENERAL: "general",
    BedType.ICU: "ICU",
    BedType.MATERNITY_SPECIALIST: "maternity/specialist",
}

_ALGORITHM_LABELS: Mapping[AlgorithmName, str] = {
    AlgorithmName.GREEDY: "greedy nearest-facility",
    AlgorithmName.WEIGHTED: "weighted multi-criteria",
    AlgorithmName.URGENCY_ADAPTIVE: "urgency-adaptive",
}


class AllocationService:
    """Runs an emergency through the matching pipeline and audits it (docs/01 §3.3)."""

    def __init__(
        self,
        session: AsyncSession,
        travel_service: TravelTimeService,
        study_parameters: StudyParameters | None = None,
    ) -> None:
        self._session = session
        self._travel = travel_service
        # Defaults reproduce parameters.py exactly; a sensitivity variant supplies its own.
        self._params = study_parameters or StudyParameters.defaults()

    async def evaluate(self, request: AllocationRequest) -> AllocationOutcome:
        """Run the pipeline and return the decision, WITHOUT persisting the audit record."""
        algorithm_config, bed_source = await self._resolve_context(request)
        algorithm_name = select_algorithm(algorithm_config, request.urgency)
        urgency = request.urgency or DEFAULT_URGENCY_WHEN_MISSING
        radius = self._params.radius_minutes[urgency]
        weights = self._params.weight_for(algorithm_name, urgency)

        facilities = await self._facilities_supporting(request.required_bed_type)
        facility_by_id = {str(f.id): f for f in facilities}
        candidates = await self._build_candidates(request, facilities, bed_source)

        result = run_scoring(
            candidates, urgency, radius, algorithm_name, self._params.capability_matrix, weights
        )

        if result.selected is None:
            return self._escalation_outcome(
                candidates, radius, urgency, algorithm_name, facility_by_id, request
            )
        return self._recommendation_outcome(result, algorithm_name, facility_by_id, request)

    async def allocate(self, request: AllocationRequest) -> AllocationOutcome:
        """Evaluate the request, persist the ``emergency_request`` audit record, return it."""
        outcome = await self.evaluate(request)
        record = self._to_audit_record(request, outcome)
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        outcome.id = record.id
        return outcome

    # --- context resolution -------------------------------------------------

    async def _resolve_context(
        self, request: AllocationRequest
    ) -> tuple[AlgorithmName | None, BedDataSource]:
        """Resolve the simulation algorithm (if any) and the bed source for the request."""
        if request.simulation_session_id is None:
            return None, LocalBedCountSource(self._session)
        sim = await self._session.get(SimulationSession, request.simulation_session_id)
        if sim is None:
            raise SimulationSessionNotFoundError(str(request.simulation_session_id))
        return sim.algorithm_config, SimulationDataSource(self._session, sim.id)

    async def _facilities_supporting(self, bed_type: BedType) -> list[Facility]:
        """Return facilities that offer the requested bed type (the candidate universe)."""
        query = select(Facility).where(Facility.supported_bed_types.contains([bed_type]))
        return list((await self._session.scalars(query)).all())

    async def _build_candidates(
        self,
        request: AllocationRequest,
        facilities: Sequence[Facility],
        bed_source: BedDataSource,
    ) -> list[Candidate]:
        """Fetch travel time and available beds for each facility, building candidates."""
        origin = Coordinate(request.patient_lat, request.patient_lon)
        candidates: list[Candidate] = []
        for facility in facilities:
            travel = await self._travel.travel_time(
                origin, Coordinate(float(facility.latitude), float(facility.longitude))
            )
            beds = await bed_source.get_available_beds(facility.id, request.required_bed_type)
            candidates.append(
                Candidate(
                    facility_id=str(facility.id),
                    tier=facility.tier,
                    travel_time_min=travel.minutes,
                    available_beds=beds,
                    is_estimated_travel_time=travel.is_estimated,
                )
            )
        return candidates

    # --- outcome construction ----------------------------------------------

    def _recommendation_outcome(
        self,
        result: ScoringResult,
        algorithm_name: AlgorithmName,
        facility_by_id: Mapping[str, Facility],
        request: AllocationRequest,
    ) -> AllocationOutcome:
        assert result.selected is not None  # caller guarantees a winner exists
        selected: ScoredCandidate = result.selected
        facility = facility_by_id[selected.candidate.facility_id]
        recommendation = FacilityRecommendation(
            facility_id=facility.id,
            name=facility.name,
            tier=facility.tier,
            available_beds=selected.candidate.available_beds,
            travel_time_minutes=selected.candidate.travel_time_min,
            is_estimated_travel_time=selected.candidate.is_estimated_travel_time,
            latitude=float(facility.latitude),
            longitude=float(facility.longitude),
            contact_phone=facility.contact_phone,
            capability_match=selected.c_hat,
        )
        reason = self._recommendation_reason(
            algorithm_name, len(result.passing), request.required_bed_type
        )
        return AllocationOutcome(
            status=Status.ALLOCATED,
            algorithm_used=algorithm_name,
            candidates_evaluated=len(result.passing),
            selection_reason=reason,
            weight_vector=result.weights,
            recommended=recommendation,
            scored=result.scored,
        )

    def _escalation_outcome(
        self,
        candidates: Sequence[Candidate],
        radius: float,
        urgency: Urgency,
        algorithm_name: AlgorithmName,
        facility_by_id: Mapping[str, Facility],
        request: AllocationRequest,
    ) -> AllocationOutcome:
        within, outside = escalation_fallbacks(candidates, radius)
        reason = (
            f"No reachable facility within R({urgency.value})={int(radius)} min had an "
            f"available {_BED_LABELS[request.required_bed_type]} bed."
        )
        return AllocationOutcome(
            status=Status.ESCALATED,
            algorithm_used=algorithm_name,
            candidates_evaluated=0,
            selection_reason=reason,
            nearest_within_radius=self._to_brief(within, facility_by_id),
            nearest_available_outside_radius=self._to_brief(outside, facility_by_id),
        )

    @staticmethod
    def _to_brief(
        candidate: Candidate | None, facility_by_id: Mapping[str, Facility]
    ) -> FacilityBrief | None:
        if candidate is None:
            return None
        facility = facility_by_id[candidate.facility_id]
        return FacilityBrief(
            facility_id=facility.id,
            name=facility.name,
            travel_time_minutes=candidate.travel_time_min,
            available_beds=candidate.available_beds,
        )

    @staticmethod
    def _recommendation_reason(algorithm_name: AlgorithmName, count: int, bed_type: BedType) -> str:
        label = _BED_LABELS[bed_type]
        if algorithm_name == AlgorithmName.GREEDY:
            return f"Nearest of {count} reachable facilities with an available {label} bed."
        return (
            f"Lowest {_ALGORITHM_LABELS[algorithm_name]} score among {count} reachable "
            f"facilities with an available {label} bed."
        )

    def _to_audit_record(
        self, request: AllocationRequest, outcome: AllocationOutcome
    ) -> EmergencyRequest:
        """Map a request + outcome onto the persisted ``emergency_request`` row (docs/02 §2.3)."""
        recommendation = outcome.recommended
        return EmergencyRequest(
            patient_lat=Decimal(str(request.patient_lat)),
            patient_lon=Decimal(str(request.patient_lon)),
            urgency=request.urgency,
            required_bed_type=request.required_bed_type,
            simulation_session_id=request.simulation_session_id,
            algorithm_used=outcome.algorithm_used,
            weight_vector=outcome.weight_vector.model_dump() if outcome.weight_vector else None,
            selection_reason=outcome.selection_reason,
            recommended_facility_id=recommendation.facility_id if recommendation else None,
            travel_time_minutes=(
                Decimal(str(recommendation.travel_time_minutes)) if recommendation else None
            ),
            is_estimated_travel_time=(
                recommendation.is_estimated_travel_time if recommendation else False
            ),
            capability_match=(
                Decimal(str(recommendation.capability_match)) if recommendation else None
            ),
            candidates_evaluated=outcome.candidates_evaluated,
            status=outcome.status,
        )
