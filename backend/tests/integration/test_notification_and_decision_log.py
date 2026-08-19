"""Notification (FR19) and decision_log (FR12) persistence tests.

FR19: confirmation produces exactly one gateway call carrying urgency, bed type, ETA, and
reservation reference, and the message is recorded. FR12: recomputing the score from the
logged candidates + weights must reproduce the logged ranking exactly — this checks the
logged shape carries what that recomputation needs, not the recomputation itself (that is
docs/12 §2's deterministic-vector job, over ``domain/allocation/scoring.py`` directly).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bed_count import BedCount
from app.db.models.decision_log import DecisionLog
from app.db.models.facility import Facility
from app.db.models.notification import Notification
from app.domain.allocation.service import AllocationRequest, AllocationService
from app.domain.notify.base import DeliveryResult, SMSGateway
from app.domain.travel.base import Coordinate, TravelTimeResult, TravelTimeService
from app.parameters import BedType, NotificationDeliveryStatus, Tier, Urgency


class _StubTravel(TravelTimeService):
    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        return TravelTimeResult(minutes=12.0, is_estimated=False)


class _RecordingGateway(SMSGateway):
    """Records every send() call so the test can assert exactly one happened."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def send(self, recipient_msisdn: str, message: str) -> DeliveryResult:
        self.calls.append((recipient_msisdn, message))
        return DeliveryResult(delivered=True)


async def _make_icu_facility(session: AsyncSession) -> Facility:
    facility = Facility(
        name="Notify Test Facility",
        latitude="5.60",
        longitude="-0.20",
        tier=Tier.TERTIARY,
        supported_bed_types=[BedType.ICU],
        contact_phone="+233555000111",
    )
    session.add(facility)
    await session.flush()
    session.add(BedCount(facility_id=facility.id, bed_type=BedType.ICU, available=1, capacity=1))
    await session.commit()
    return facility


async def test_confirmed_allocation_sends_exactly_one_sms_with_documented_fields(
    db_session: AsyncSession,
) -> None:
    facility = await _make_icu_facility(db_session)
    gateway = _RecordingGateway()
    service = AllocationService(db_session, _StubTravel(), sms_gateway=gateway)

    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=5.60,
            patient_lon=-0.20,
            required_bed_type=BedType.ICU,
            urgency=Urgency.CRITICAL,
        )
    )

    assert len(gateway.calls) == 1
    recipient, _message = gateway.calls[0]
    assert recipient == facility.contact_phone

    notification = await db_session.scalar(
        select(Notification).where(Notification.allocation_id == outcome.id)
    )
    assert notification is not None
    assert notification.delivery_status == NotificationDeliveryStatus.SENT
    assert notification.sent_at is not None
    assert notification.payload["urgency"] == "critical"
    assert notification.payload["bed_type"] == "icu"
    assert notification.payload["eta_minutes"] == 12.0
    assert notification.payload["reference"] == str(outcome.id)


async def test_failed_delivery_is_recorded_as_failed(db_session: AsyncSession) -> None:
    await _make_icu_facility(db_session)

    class _FailingGateway(SMSGateway):
        async def send(self, recipient_msisdn: str, message: str) -> DeliveryResult:
            return DeliveryResult(delivered=False, detail="gateway timeout")

    service = AllocationService(db_session, _StubTravel(), sms_gateway=_FailingGateway())
    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=5.60, patient_lon=-0.20, required_bed_type=BedType.ICU,
            urgency=Urgency.CRITICAL,
        )
    )

    notification = await db_session.scalar(
        select(Notification).where(Notification.allocation_id == outcome.id)
    )
    assert notification is not None
    assert notification.delivery_status == NotificationDeliveryStatus.FAILED
    assert notification.sent_at is None


async def test_decision_log_carries_every_candidate_with_score_breakdown(
    db_session: AsyncSession,
) -> None:
    await _make_icu_facility(db_session)
    service = AllocationService(db_session, _StubTravel())

    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=5.60, patient_lon=-0.20, required_bed_type=BedType.ICU,
            urgency=Urgency.CRITICAL,
        )
    )

    log = await db_session.scalar(
        select(DecisionLog).where(DecisionLog.allocation_id == outcome.id)
    )
    assert log is not None
    assert len(log.candidates) == 1
    candidate = log.candidates[0]
    expected_keys = {
        "facility_id", "tier", "travel_time_min", "available_beds",
        "t_hat", "b_hat", "c_hat", "score",
    }
    assert expected_keys <= set(candidate)
    assert log.weights == {"w_t": 0.50, "w_b": 0.10, "w_c": 0.40}
    assert log.parameters_snapshot["radius_minutes"]["critical"] == 30


async def test_decision_log_persists_on_escalation_with_rejected_reason(
    db_session: AsyncSession,
) -> None:
    service = AllocationService(db_session, _StubTravel())  # no facility seeded at all

    outcome = await service.allocate(
        AllocationRequest(
            patient_lat=5.60, patient_lon=-0.20, required_bed_type=BedType.ICU,
            urgency=Urgency.CRITICAL,
        )
    )

    log = await db_session.scalar(
        select(DecisionLog).where(DecisionLog.allocation_id == outcome.id)
    )
    assert log is not None
    assert log.candidates == []
    assert log.rejected_reason == outcome.selection_reason
