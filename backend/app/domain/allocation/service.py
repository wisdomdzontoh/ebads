"""Emergency Request & Allocation Service (docs/01 §3.3, §7, docs/03, docs/04 §4).

``evaluate`` is the pure(ish) matching pipeline: resolve the algorithm + bed source, build
candidates (travel time + available beds) over facilities that support the requested bed
type, run the shared scoring pipeline, and return a recommendation or a structured
escalation. It performs no reservation and is reused unchanged by the simulation engine.

``allocate`` is the live-only path built on top of it (docs/01 §7): it persists the request,
then — for a scored recommendation — attempts the compare-and-set reservation loop over the
already-ranked candidates (``domain/reservation/manager.py``, FR8/FR9), falling through on
``VersionConflict`` with no re-query. On success it persists the ``allocation``,
``reservation``, ``decision_log`` (FR12) and sends the facility SMS (FR19). If every
candidate conflicts (a genuine race between scoring and reserving), it degrades to an
escalation rather than ever double-committing a bed — reads are advisory, the compare-and-set
alone is authoritative (docs/01 §7).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.allocation import Allocation
from app.db.models.decision_log import DecisionLog
from app.db.models.emergency_request import EmergencyRequest
from app.db.models.facility import Facility
from app.db.models.notification import Notification
from app.db.models.reservation import Reservation
from app.db.models.simulation_session import SimulationSession
from app.domain.allocation.candidate import Candidate, ScoredCandidate
from app.domain.allocation.hard_filter import escalation_fallbacks
from app.domain.allocation.scoring import ScoringResult, rank_by_score, run_scoring
from app.domain.allocation.selector import select_algorithm
from app.domain.allocation.study_parameters import StudyParameters
from app.domain.beds.base import BedDataSource
from app.domain.beds.manual_adapter import ManualAdapter
from app.domain.beds.simulation_source import SimulationDataSource
from app.domain.notify.base import SMSGateway
from app.domain.notify.log_gateway import LogGateway
from app.domain.reservation.manager import reserve_from_ranking
from app.domain.travel.base import Coordinate, TravelTimeService
from app.parameters import (
    DEFAULT_URGENCY_WHEN_MISSING,
    HAVERSINE_SPEED_KMH,
    RESERVATION_GRACE_MIN,
    SMS_CHANNEL,
    AlgorithmName,
    AllocationStatus,
    BedType,
    NotificationChannel,
    NotificationDeliveryStatus,
    Status,
    Tier,
    Urgency,
    WeightVector,
)

# [IMPL] Converts an urgency radius from minutes to metres for the PostGIS pre-filter, at
# the same urban speed factor the Haversine fallback uses (docs/03 §2: "radius_metres
# derives from R(u) at the configured urban speed factor").
_METRES_PER_MINUTE = HAVERSINE_SPEED_KMH * 1000 / 60


def _radius_metres(radius_minutes: float) -> float:
    return radius_minutes * _METRES_PER_MINUTE


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
    # The authenticated dispatcher, for live requests (NFR8). None for simulation-generated
    # requests, which have no human submitter.
    dispatcher_id: uuid.UUID | None = None


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
    """The decision for one request: a recommendation or an escalation (docs/04 §4).

    ``status`` is the *pure* scoring verdict (``evaluate``'s own vocabulary — see the module
    docstring on why the live reservation lifecycle is a separate enum). ``eta_minutes`` and
    ``attempts`` are set by ``allocate`` after the reservation loop runs; they are meaningless
    on an ``evaluate``-only outcome (simulation's), where they stay at their defaults.
    """

    status: Status
    algorithm_used: AlgorithmName
    candidates_evaluated: int
    selection_reason: str
    weight_vector: WeightVector | None = None
    recommended: FacilityRecommendation | None = None
    nearest_within_radius: FacilityBrief | None = None
    nearest_available_outside_radius: FacilityBrief | None = None
    # Full scored set, for the simulation step trace (Phase 4) and the reservation loop.
    # Empty on escalation.
    scored: list[ScoredCandidate] = field(default_factory=list)
    # Set by allocate() once a reservation is confirmed; None otherwise.
    eta_minutes: float | None = None
    attempts: int = 0
    # Set after persistence by allocate() — the allocation id (not the emergency_request id).
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
    """Runs an emergency through the matching pipeline, then (live only) reserves it."""

    def __init__(
        self,
        session: AsyncSession,
        travel_service: TravelTimeService,
        study_parameters: StudyParameters | None = None,
        sms_gateway: SMSGateway | None = None,
    ) -> None:
        self._session = session
        self._travel = travel_service
        # Defaults reproduce parameters.py exactly; a sensitivity variant supplies its own.
        self._params = study_parameters or StudyParameters.defaults()
        self._sms = sms_gateway or LogGateway()

    async def evaluate(self, request: AllocationRequest) -> AllocationOutcome:
        """Run the pipeline and return the decision, WITHOUT reserving or persisting anything."""
        algorithm_config, bed_source = await self._resolve_context(request)
        algorithm_name = select_algorithm(algorithm_config, request.urgency)
        urgency = request.urgency or DEFAULT_URGENCY_WHEN_MISSING
        radius = self._params.radius_minutes[urgency]
        weights = self._params.weight_for(algorithm_name, urgency)
        origin = Coordinate(request.patient_lat, request.patient_lon)

        # Primary path: PostGIS-indexed retrieval within the urgency radius (FR3, NFR2) — the
        # only query in this method that must scale with registry size, since this is the
        # common case (an admissible facility is usually nearby).
        nearby = await self._spatial_retrieve(origin, radius, request.required_bed_type)
        facility_by_id = {str(f.id): f for f in nearby}
        candidates = await self._build_candidates(request, nearby, bed_source)

        result = run_scoring(
            candidates, urgency, radius, algorithm_name, self._params.capability_matrix, weights
        )

        if result.selected is None:
            # Escalation is rare by construction (it means nothing admissible was even
            # nearby) — visibility beyond the spatial radius is required for the "nearest
            # available outside radius" fallback (FR11), so this path alone accepts an
            # unbounded fetch. NFR2/S3 target the common path above, not this one.
            all_facilities = await self._facilities_supporting(request.required_bed_type)
            all_candidates = await self._build_candidates(request, all_facilities, bed_source)
            facility_by_id = {str(f.id): f for f in all_facilities}
            return self._escalation_outcome(
                all_candidates, radius, urgency, algorithm_name, facility_by_id, request
            )
        return self._recommendation_outcome(result, algorithm_name, facility_by_id, request)

    async def allocate(self, request: AllocationRequest) -> AllocationOutcome:
        """Evaluate, then (docs/01 §7) commit a reservation and notify — the live path.

        Persists ``emergency_request`` unconditionally. A scoring escalation persists an
        ``escalated`` allocation with no reservation attempt. A scoring recommendation
        attempts the CAS loop (FR8/FR9); on success it persists ``allocation`` (confirmed),
        ``reservation``, ``decision_log`` and sends the facility SMS (FR19). If the loop
        exhausts every candidate (all conflicted — a genuine race), it degrades to an
        escalation instead: reads were only ever advisory (docs/01 §7).
        """
        outcome = await self.evaluate(request)
        emergency_request = self._new_emergency_request(request)
        self._session.add(emergency_request)
        await self._session.flush()  # assigns emergency_request.id

        if outcome.status == Status.ESCALATED:
            await self._persist_escalation(emergency_request.id, outcome, attempts=0)
            await self._session.commit()
            return outcome

        urgency = request.urgency or DEFAULT_URGENCY_WHEN_MISSING
        radius = self._params.radius_minutes[urgency]
        _, bed_source = await self._resolve_context(request)
        reservation_result = await reserve_from_ranking(
            bed_source, outcome.scored, request.required_bed_type
        )

        if reservation_result.reserved is None:
            # Every candidate conflicted between scoring and reserving — a race, not a
            # planning failure. Degrade to escalation rather than fabricate a commitment.
            race_outcome = await self._race_exhausted_outcome(
                outcome, radius, reservation_result.attempts
            )
            await self._persist_escalation(
                emergency_request.id, race_outcome, attempts=reservation_result.attempts
            )
            await self._session.commit()
            return race_outcome

        winner = reservation_result.reserved
        facility = await self._session.get(Facility, uuid.UUID(winner.candidate.facility_id))
        assert facility is not None  # just fetched as a candidate; cannot vanish mid-request
        eta_minutes = winner.candidate.travel_time_min

        allocation = Allocation(
            request_id=emergency_request.id,
            facility_id=facility.id,
            strategy_used=outcome.algorithm_used,
            weight_vector=outcome.weight_vector.model_dump() if outcome.weight_vector else None,
            score=Decimal(str(winner.score)),
            travel_time_minutes=Decimal(str(winner.candidate.travel_time_min)),
            is_estimated_travel_time=winner.candidate.is_estimated_travel_time,
            eta_minutes=Decimal(str(eta_minutes)),
            capability_match=Decimal(str(winner.c_hat)),
            candidates_evaluated=outcome.candidates_evaluated,
            attempts=reservation_result.attempts,
            selection_reason=outcome.selection_reason,
            status=AllocationStatus.CONFIRMED,
        )
        self._session.add(allocation)
        await self._session.flush()  # assigns allocation.id

        self._session.add(self._new_decision_log(allocation.id, outcome))

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=eta_minutes + RESERVATION_GRACE_MIN)
        self._session.add(
            Reservation(
                allocation_id=allocation.id,
                facility_id=facility.id,
                bed_type=request.required_bed_type,
                created_at=now,
                expires_at=expires_at,
            )
        )

        self._session.add(
            await self._send_reservation_sms(allocation, facility, request, eta_minutes)
        )

        await self._session.commit()

        outcome.recommended = FacilityRecommendation(
            facility_id=facility.id,
            name=facility.name,
            tier=facility.tier,
            available_beds=winner.candidate.available_beds,
            travel_time_minutes=winner.candidate.travel_time_min,
            is_estimated_travel_time=winner.candidate.is_estimated_travel_time,
            latitude=float(facility.latitude),
            longitude=float(facility.longitude),
            contact_phone=facility.contact_phone,
            capability_match=winner.c_hat,
        )
        outcome.eta_minutes = eta_minutes
        outcome.attempts = reservation_result.attempts
        outcome.id = allocation.id
        return outcome

    async def _race_exhausted_outcome(
        self, outcome: AllocationOutcome, radius: float, attempts: int
    ) -> AllocationOutcome:
        """Build the escalation outcome for a reservation loop that conflicted on every candidate.

        Nothing is known to be "outside radius" here — every candidate already passed the
        hard filter, so (unlike ``evaluate``'s hard-filter-empty escalation, which explicitly
        widens the query) there is no broader fetch to draw that fallback from; it stays None.
        """
        candidates = [sc.candidate for sc in outcome.scored]
        within, _ = escalation_fallbacks(candidates, radius)
        nearest_within_radius = None
        if within is not None:
            facility = await self._session.get(Facility, uuid.UUID(within.facility_id))
            assert facility is not None  # just fetched as a candidate; cannot vanish mid-request
            nearest_within_radius = FacilityBrief(
                facility_id=facility.id,
                name=facility.name,
                travel_time_minutes=within.travel_time_min,
                available_beds=within.available_beds,
            )
        return AllocationOutcome(
            status=Status.ESCALATED,
            algorithm_used=outcome.algorithm_used,
            candidates_evaluated=outcome.candidates_evaluated,
            selection_reason=(
                f"All {attempts} candidate(s) were reserved by a concurrent request "
                "before this one could commit."
            ),
            nearest_within_radius=nearest_within_radius,
        )

    # --- persistence helpers -------------------------------------------------

    def _new_emergency_request(self, request: AllocationRequest) -> EmergencyRequest:
        return EmergencyRequest(
            dispatcher_id=request.dispatcher_id,
            patient_lat=Decimal(str(request.patient_lat)),
            patient_lon=Decimal(str(request.patient_lon)),
            urgency=request.urgency,
            required_bed_type=request.required_bed_type,
            simulation_session_id=request.simulation_session_id,
        )

    async def _persist_escalation(
        self, request_id: uuid.UUID, outcome: AllocationOutcome, attempts: int
    ) -> None:
        allocation = Allocation(
            request_id=request_id,
            facility_id=None,
            strategy_used=outcome.algorithm_used,
            weight_vector=outcome.weight_vector.model_dump() if outcome.weight_vector else None,
            candidates_evaluated=outcome.candidates_evaluated,
            attempts=attempts,
            selection_reason=outcome.selection_reason,
            status=AllocationStatus.ESCALATED,
        )
        self._session.add(allocation)
        await self._session.flush()
        self._session.add(
            self._new_decision_log(allocation.id, outcome, rejected_reason=outcome.selection_reason)
        )
        outcome.id = allocation.id

    def _new_decision_log(
        self,
        allocation_id: uuid.UUID,
        outcome: AllocationOutcome,
        rejected_reason: str | None = None,
    ) -> DecisionLog:
        """Persist every scored candidate for FR12 replay (docs/02 §3.8)."""
        return DecisionLog(
            allocation_id=allocation_id,
            candidates=[
                {
                    "facility_id": sc.candidate.facility_id,
                    "tier": sc.candidate.tier.value,
                    "travel_time_min": sc.candidate.travel_time_min,
                    "available_beds": sc.candidate.available_beds,
                    "t_hat": sc.t_hat,
                    "b_hat": sc.b_hat,
                    "c_hat": sc.c_hat,
                    "score": sc.score,
                }
                for sc in rank_by_score(outcome.scored)
            ],
            weights=outcome.weight_vector.model_dump() if outcome.weight_vector else None,
            parameters_snapshot={
                "radius_minutes": {u.value: r for u, r in self._params.radius_minutes.items()},
                "capability_matrix": {
                    u.value: {t.value: v for t, v in row.items()}
                    for u, row in self._params.capability_matrix.items()
                },
            },
            rejected_reason=rejected_reason,
        )

    async def _send_reservation_sms(
        self,
        allocation: Allocation,
        facility: Facility,
        request: AllocationRequest,
        eta_minutes: float,
    ) -> Notification:
        """Send + record the FR19 SMS: urgency, bed type, ETA, reservation reference."""
        urgency = request.urgency or DEFAULT_URGENCY_WHEN_MISSING
        message = (
            f"EBADS: incoming {urgency.value} patient, {_BED_LABELS[request.required_bed_type]} "
            f"bed, ETA {eta_minutes:.0f} min. Reference {allocation.id}."
        )
        payload = {
            "urgency": urgency.value,
            "bed_type": request.required_bed_type.value,
            "eta_minutes": eta_minutes,
            "reference": str(allocation.id),
        }
        result = await self._sms.send(facility.contact_phone, message)
        return Notification(
            allocation_id=allocation.id,
            channel=NotificationChannel(SMS_CHANNEL),
            recipient=facility.contact_phone,
            payload=payload,
            sent_at=datetime.now(UTC) if result.delivered else None,
            delivery_status=(
                NotificationDeliveryStatus.SENT
                if result.delivered
                else NotificationDeliveryStatus.FAILED
            ),
            attempts=1,
        )

    # --- context resolution -------------------------------------------------

    async def _resolve_context(
        self, request: AllocationRequest
    ) -> tuple[AlgorithmName | None, BedDataSource]:
        """Resolve the simulation algorithm (if any) and the bed source for the request."""
        if request.simulation_session_id is None:
            return None, ManualAdapter(self._session)
        sim = await self._session.get(SimulationSession, request.simulation_session_id)
        if sim is None:
            raise SimulationSessionNotFoundError(str(request.simulation_session_id))
        return sim.algorithm_config, SimulationDataSource(self._session, sim.id)

    async def _facilities_supporting(self, bed_type: BedType) -> list[Facility]:
        """Return every facility offering the requested bed type, unbounded by distance.

        Used only on the (rare) escalation path — see ``evaluate``'s docstring note. The
        common path is ``_spatial_retrieve``, which is index-backed (FR3).
        """
        query = select(Facility).where(Facility.supported_bed_types.contains([bed_type]))
        return list((await self._session.scalars(query)).all())

    @staticmethod
    def spatial_retrieve_query(
        origin: Coordinate, radius_minutes: float, bed_type: BedType
    ) -> Select[tuple[Facility]]:
        """Build the FR3 spatial retrieval query.

        Extracted so a test can ``EXPLAIN`` this exact statement, not a hand-duplicated copy.

        ``ST_DWithin`` against ``facility.location`` uses the GIST index (migration 0007) —
        the query plan showing an index scan rather than a sequential scan is FR3's accept
        criterion. The radius here is a straight-line pre-filter at the configured urban
        speed factor; it is deliberately generous (a road route is never shorter than the
        straight line), and the exact cutoff on real travel time still happens afterward in
        the hard filter (``run_scoring`` → ``filter_candidates``), so a coarse pre-filter can
        only ever admit extra candidates, never wrongly exclude an admissible one under that
        same speed-factor assumption.
        """
        origin_point = WKTElement(f"POINT({origin.longitude} {origin.latitude})", srid=4326)
        return select(Facility).where(
            func.ST_DWithin(
                Facility.location,
                func.cast(origin_point, Geography),
                _radius_metres(radius_minutes),
            ),
            Facility.supported_bed_types.contains([bed_type]),
        )

    async def _spatial_retrieve(
        self, origin: Coordinate, radius_minutes: float, bed_type: BedType
    ) -> list[Facility]:
        """PostGIS spatial retrieval within ``radius_minutes``, filtered by bed type.

        (docs/03 §2.)
        """
        query = self.spatial_retrieve_query(origin, radius_minutes, bed_type)
        return list((await self._session.scalars(query)).all())

    async def _build_candidates(
        self,
        request: AllocationRequest,
        facilities: Sequence[Facility],
        bed_source: BedDataSource,
    ) -> list[Candidate]:
        """Fetch travel time and available beds for each facility, building candidates.

        ``fetch`` returns every bed type a facility tracks (docs/01 §5); only the requested
        type's count feeds the candidate. This is the advisory read the pipeline scores
        against — the reservation step (docs/01 §7) is what actually commits a bed, via the
        same source's ``reserve``.
        """
        origin = Coordinate(request.patient_lat, request.patient_lon)
        candidates: list[Candidate] = []
        for facility in facilities:
            travel = await self._travel.travel_time(
                origin, Coordinate(float(facility.latitude), float(facility.longitude))
            )
            bed_states = await bed_source.fetch(facility.id)
            matching_state = next(
                (bs for bs in bed_states if bs.bed_type == request.required_bed_type), None
            )
            candidates.append(
                Candidate(
                    facility_id=str(facility.id),
                    tier=facility.tier,
                    travel_time_min=travel.minutes,
                    available_beds=matching_state.available_beds if matching_state else 0,
                    is_estimated_travel_time=travel.is_estimated,
                    version=matching_state.version if matching_state else 0,
                )
            )
        return candidates

    # --- outcome construction (evaluate() only — pure) ----------------------

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
