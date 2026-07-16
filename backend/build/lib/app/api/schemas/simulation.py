"""Request/response schemas for the Simulation Service (docs/04-api-spec.md §5).

Covers session creation (with occupancy validated against the study's fixed scenario set),
the automatic-run summary metrics, the interactive-step decision trace (candidates + scores +
selection), and the results view (per-event records + aggregated metrics). Sensitivity
override configs are accepted in the body for forward compatibility but must be null in this
phase — the field validator rejects non-null values rather than letting them be ignored.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.parameters import (
    OCCUPANCY_SCENARIOS,
    AlgorithmName,
    BedType,
    Status,
    Urgency,
    WeightVector,
)


class SimulationSessionCreate(BaseModel):
    """Body of ``POST /api/v1/simulation/sessions`` (docs/04 §5)."""

    algorithm_config: AlgorithmName
    occupancy_scenario: float
    events_planned: int = Field(gt=0)
    random_seed: int
    # Accepted for forward-compatibility; must be null until the sensitivity pipeline (Phase 5).
    weight_config: dict[str, Any] | None = None
    radius_config: dict[str, Any] | None = None
    capability_config: dict[str, Any] | None = None

    @field_validator("occupancy_scenario")
    @classmethod
    def _occupancy_in_scenario_set(cls, value: float) -> float:
        """Only the study's fixed occupancy scenarios are allowed (docs/09 §12.5)."""
        if value not in OCCUPANCY_SCENARIOS:
            raise ValueError(
                f"occupancy_scenario must be one of {OCCUPANCY_SCENARIOS}, got {value}"
            )
        return value

    @field_validator("weight_config", "radius_config", "capability_config")
    @classmethod
    def _overrides_not_supported_yet(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """Reject non-null overrides — applied by the sensitivity pipeline (Phase 5), not here."""
        if value is not None:
            raise ValueError(
                "sensitivity overrides (weight/radius/capability_config) are applied by the "
                "evaluation pipeline (Phase 5); send null for the main simulation grid"
            )
        return value


class SimulationSessionRead(BaseModel):
    """A session's configuration plus its derived progress (docs/04 §5 GET session)."""

    id: uuid.UUID
    algorithm_config: AlgorithmName
    occupancy_scenario: float
    events_planned: int
    random_seed: int
    created_at: datetime
    status: str
    events_processed: int


class RunMetricsRead(BaseModel):
    """Aggregated per-run metrics (docs/07 §8). Means over empty sets are null, not zero."""

    atbp: float | None
    frr: float
    mcee: float
    cm: float | None
    cm_critical: float | None
    events_total: int
    events_allocated: int
    events_escalated: int


class RunSummary(BaseModel):
    """Response of ``POST .../run`` — the metrics for the completed automatic run (docs/04 §5)."""

    session_id: uuid.UUID
    events_processed: int
    status: str
    metrics: RunMetricsRead


class StepCandidate(BaseModel):
    """One scored candidate in the interactive-step trace (docs/04 §5)."""

    facility_id: uuid.UUID
    travel_time_minutes: float
    available_beds: int
    t_hat: float
    b_hat: float
    c_hat: float
    score: float


class StepTrace(BaseModel):
    """The full decision trace for one stepped event (docs/04 §5, thesis §3.12.2)."""

    event_index: int
    candidates: list[StepCandidate]
    selected_facility_id: uuid.UUID | None
    algorithm_used: AlgorithmName
    weight_vector: WeightVector | None
    status: Status


class SimulationEventRead(BaseModel):
    """One persisted per-event record (docs/02 §2.6) for the results view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_index: int
    virtual_arrival_min: float
    urgency: Urgency
    required_bed_type: BedType
    patient_lat: float
    patient_lon: float
    recommended_facility_id: uuid.UUID | None
    travel_time_minutes: float | None
    time_to_bed_placement_min: float | None
    capability_match: float | None
    candidates_evaluated: int
    status: Status
    los_minutes: float | None
    bed_release_virtual_min: float | None


class SimulationResults(BaseModel):
    """Response of ``GET .../results`` — session, metrics, and every per-event record."""

    session: SimulationSessionRead
    metrics: RunMetricsRead
    events: list[SimulationEventRead]
