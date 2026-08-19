"""Researcher-defined constants — the single source of truth for every number in EBADS.

This module mirrors ``docs/09-parameters.md`` one-for-one. Logic code anywhere in the
engine, simulation, and analysis layers MUST import its constants from here and never
hardcode a value (``docs/14-coding-standards.md`` §1). Centralising the numbers in one
place is what makes the study auditable and the sensitivity analysis reproducible.

Every value below is taken from the thesis unless tagged ``[IMPL]`` in a comment, which
marks an implementation default not fixed by the thesis (to be confirmed with the
researcher before any evaluation run).

Validation: ``validate_parameters()`` runs the six load-time checks from
``docs/09-parameters.md`` §12 at import. If any researcher-defined constant is internally
inconsistent (e.g. a weight row that does not sum to 1.0), import fails loudly rather than
letting a silently-wrong configuration reach a simulation run.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

# Tolerance for floating-point sum checks (weights/distributions == 1.0).
# docs/09-parameters.md §12.1 specifies ±1e-9 for the weight rows; the same bound is
# reused for the urgency/bed-type distributions.
SUM_TOLERANCE: float = 1e-9


class ParameterValidationError(Exception):
    """Raised when a researcher-defined constant violates a docs/09 §12 invariant."""


# ---------------------------------------------------------------------------
# 1. Enumerations (docs/09-parameters.md §1)
# ---------------------------------------------------------------------------


class Urgency(StrEnum):
    """Patient acuity level. Drives the travel-time radius and the Algorithm 3 weights."""

    CRITICAL = "critical"
    URGENT = "urgent"
    STANDARD = "standard"


class Tier(StrEnum):
    """Facility capability level, from highest (tertiary) to lowest (primary)."""

    TERTIARY = "tertiary"
    SECONDARY = "secondary"
    PRIMARY = "primary"


class BedType(StrEnum):
    """Category of bed a patient requires; a facility supports a subset of these."""

    GENERAL = "general"
    ICU = "icu"
    MATERNITY_SPECIALIST = "maternity_specialist"


class Status(StrEnum):
    """Lifecycle state of an emergency request / allocation event."""

    PENDING = "pending"
    ALLOCATED = "allocated"
    ESCALATED = "escalated"


class AlgorithmName(StrEnum):
    """The three matching algorithms (docs/03-algorithms.md §4-6)."""

    GREEDY = "greedy"
    WEIGHTED = "weighted"
    URGENCY_ADAPTIVE = "urgency_adaptive"


class Role(StrEnum):
    """The four account roles (docs/09-parameters.md §1, EBADS_PRD.md §2).

    Every ``user_account`` carries exactly one. ``system_administrator`` and ``dispatcher``
    are unscoped (``facility_id`` null); ``facility_administrator`` and ``facility_staff``
    are scoped to exactly one facility — enforced by a DB CHECK constraint, not just here.
    """

    SYSTEM_ADMINISTRATOR = "system_administrator"
    FACILITY_ADMINISTRATOR = "facility_administrator"
    FACILITY_STAFF = "facility_staff"
    DISPATCHER = "dispatcher"


class PermissionAction(StrEnum):
    """What a permission row grants (docs/02-data-model.md §2.2). [IMPL] enum spelling."""

    READ = "read"
    WRITE = "write"
    APPROVE = "approve"


class PermissionScope(StrEnum):
    """How far a permission reaches (docs/02-data-model.md §2.2).

    ``own_facility`` is resolved against the caller's ``user_account.facility_id`` by the
    RBAC dependency; ``all`` is unscoped.
    """

    OWN_FACILITY = "own_facility"
    ALL = "all"


class UserStatus(StrEnum):
    """Account lifecycle state (docs/02-data-model.md §2.3). [IMPL] enum spelling."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class FacilityRequestStatus(StrEnum):
    """Registration-request lifecycle (docs/02-data-model.md §2.4). [IMPL] enum spelling."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DataSource(StrEnum):
    """Which BedDataSource feeds a facility's live bed availability (docs/01 §5, docs/02 §3.3).

    Mirrors ``emr_adapter.adapter_type``. ``facility.active_data_source`` is nullable and
    only ever holds one of the three *non-manual* members below — null means manual
    maintenance via ``PATCH .../beds`` (docs/02 §3.1: "null ⇒ manual maintenance"); ``MANUAL``
    exists on this enum for the future ``emr_adapter`` history table (docs/02 §3.3), which
    can record an explicit "reverted to manual" entry. [IMPL] Enum spellings are an
    implementation choice; the adapter roster (docs/01 §5) is what they name.
    """

    MANUAL = "manual"  # ManualAdapter
    GHS_DATA = "ghs_data"  # GHSDataAdapter
    FHIR_R4 = "fhir_r4"  # FHIRAdapter (specified, not built)
    REST_POLLING = "rest_polling"  # RESTPollingAdapter (specified, not built)


class AllocationStatus(StrEnum):
    """Lifecycle of one live ``allocation`` (docs/09 §1, docs/02 §3.5).

    Distinct from ``Status`` (the simulation event's simpler pending/allocated/escalated —
    unchanged, Increment 5 replaces the whole module that reads it), because backdating the
    richer reservation lifecycle onto simulation would mean editing code this project has
    deliberately left untouched ahead of its scheduled replacement. This is the live path's
    enum; docs/09 §1 names it just ``Status``, but that name is already taken here. [IMPL]
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    ARRIVED = "arrived"
    EXPIRED = "expired"
    REFUSED = "refused"
    ESCALATED = "escalated"


class NotificationChannel(StrEnum):
    """Delivery channel for a facility notification (docs/02 §3.7). [IMPL] enum spelling."""

    SMS = "sms"
    PUSH = "push"


class NotificationDeliveryStatus(StrEnum):
    """Delivery outcome of one notification attempt (docs/02 §3.7). [IMPL] enum spelling."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# 2. Urgency-based travel-time radius R(u) (docs/09-parameters.md §2, thesis Table 3.2)
# ---------------------------------------------------------------------------

# Maximum road-travel time (minutes) a patient of a given urgency may be sent.
# A facility further than R(u) is excluded by the hard filter (docs/03 §2).
RADIUS_MINUTES: Mapping[Urgency, int] = {
    Urgency.CRITICAL: 30,
    Urgency.URGENT: 60,
    Urgency.STANDARD: 90,
}

# Urgency assumed when a live request omits/invalidates urgency. The Selector then runs
# Algorithm 2 (docs/03 §8), but the radius R(u) and capability lookup c_hat[u][tier] still
# need a urgency. We default to `standard` — the widest radius — so an unknown-urgency
# patient is not wrongly excluded from a reachable facility. [IMPL: not specified by the
# thesis; confirm with the researcher. Only affects the live null-urgency path — never the
# simulation, the deterministic vectors, or RB-3, which all carry an explicit urgency.]
DEFAULT_URGENCY_WHEN_MISSING: Urgency = Urgency.STANDARD


# ---------------------------------------------------------------------------
# 3. Capability-match matrix c_hat[urgency][tier] (docs/09 §3, thesis Table 3.3)
# ---------------------------------------------------------------------------

# How well a facility tier serves a patient of a given urgency, already in [0, 1].
# This is looked up directly (NOT min-max normalised) — see docs/03-algorithms.md §3.
CAPABILITY_MATRIX: Mapping[Urgency, Mapping[Tier, float]] = {
    Urgency.CRITICAL: {Tier.TERTIARY: 1.0, Tier.SECONDARY: 0.6, Tier.PRIMARY: 0.2},
    Urgency.URGENT: {Tier.TERTIARY: 0.8, Tier.SECONDARY: 1.0, Tier.PRIMARY: 0.5},
    Urgency.STANDARD: {Tier.TERTIARY: 0.5, Tier.SECONDARY: 0.8, Tier.PRIMARY: 1.0},
}


# ---------------------------------------------------------------------------
# 4-5. Algorithm weight vectors (docs/09 §4-5, thesis §3.5.5 / Table 3.5)
# ---------------------------------------------------------------------------


class WeightVector(BaseModel):
    """A scoring weight triple ``(w_t, w_b, w_c)`` that must sum to 1.0.

    The three weights apply, in order, to normalised travel time, bed scarcity, and
    capability mismatch (docs/03-algorithms.md §5-6). The sum-to-one constraint
    (docs/09-parameters.md §12.1-2) is enforced here at construction time, so any
    weight vector that reaches the rest of the system is already valid.

    Frozen so a shared weight vector cannot be mutated mid-study.
    """

    model_config = ConfigDict(frozen=True)

    w_t: float
    w_b: float
    w_c: float

    @model_validator(mode="after")
    def _must_sum_to_one(self) -> WeightVector:
        """Reject any weight triple whose components do not sum to 1.0 (±SUM_TOLERANCE)."""
        total = self.w_t + self.w_b + self.w_c
        if abs(total - 1.0) > SUM_TOLERANCE:
            raise ValueError(f"weights must sum to 1.0, got {total!r} for {self!r}")
        return self


# Algorithm 2 — fixed weights, identical for every urgency (docs/09-parameters.md §5).
# Corrected 2026-08-19: an earlier document set recorded 0.40/0.35/0.25 (docs/09 §5's own
# note: "Chapter Three is authoritative"). This constant carried the stale value until now —
# see docs/09 §5 and tests/vectors/weighted_*.json, regenerated alongside this fix.
ALGORITHM_2_WEIGHTS: WeightVector = WeightVector(w_t=0.40, w_b=0.30, w_c=0.30)

# Algorithm 3 — urgency-adaptive weights (docs/09-parameters.md §6, thesis Table 3.5).
# Corrected 2026-08-19: an earlier document set recorded critical 0.50/0.15/0.35 and
# standard 0.30/0.50/0.20 (docs/09 §6's own note). See tests/vectors/urgency_adaptive_*.json.
ALGORITHM_3_WEIGHTS: Mapping[Urgency, WeightVector] = {
    Urgency.CRITICAL: WeightVector(w_t=0.50, w_b=0.10, w_c=0.40),
    Urgency.URGENT: WeightVector(w_t=0.40, w_b=0.25, w_c=0.35),
    Urgency.STANDARD: WeightVector(w_t=0.25, w_b=0.50, w_c=0.25),
}


# ---------------------------------------------------------------------------
# 6. Normalization (docs/09 §6, thesis §3.5.2)
# ---------------------------------------------------------------------------

# Min-max tie rule: when x_max == x_min for a criterion across the candidate set, every
# normalised value collapses to this constant rather than dividing by zero (docs/03 §3).
NORMALIZATION_TIE_VALUE: float = 0.5


# ---------------------------------------------------------------------------
# 7. Travel-time service (docs/09 §7, thesis §3.5.7)
# ---------------------------------------------------------------------------

# Assumed urban road speed for the Haversine great-circle fallback used when the
# Google Distance Matrix API is unavailable. Results computed this way are always
# flagged with is_estimated_travel_time = true (docs/01-architecture.md §3.6).
HAVERSINE_SPEED_KMH: float = 30.0


# ---------------------------------------------------------------------------
# 8. Simulation parameters (docs/09 §8, thesis Table 3.8)
# ---------------------------------------------------------------------------

# Inter-arrival time between emergency events is uniform on this closed interval (minutes).
EVENT_INTERARRIVAL_MIN_MINUTES: int = 3
EVENT_INTERARRIVAL_MAX_MINUTES: int = 7

# Mix of patient acuities drawn per event (must sum to 1.0 — §12.6).
URGENCY_DISTRIBUTION: Mapping[Urgency, float] = {
    Urgency.CRITICAL: 0.20,
    Urgency.URGENT: 0.35,
    Urgency.STANDARD: 0.45,
}

# Mix of required bed types drawn per event (must sum to 1.0 — §12.6).
BED_TYPE_DISTRIBUTION: Mapping[BedType, float] = {
    BedType.GENERAL: 0.40,
    BedType.ICU: 0.30,
    BedType.MATERNITY_SPECIALIST: 0.30,
}

# The three occupancy scenarios the study sweeps (docs/09 §8; §12.5 pins the exact set).
OCCUPANCY_SCENARIOS: tuple[float, ...] = (0.75, 0.90, 1.00)

# Study grid size (docs/09 §8): 30 runs x 100 events per algorithm per scenario.
RUNS_PER_CONFIGURATION: int = 30
EVENTS_PER_RUN: int = 100


# ---------------------------------------------------------------------------
# 8.1 Simulation constants not enumerated in the thesis (docs/09 §8.1) [IMPL]
# ---------------------------------------------------------------------------
# Defaults below are placeholders required to implement the virtual clock and bed
# lifecycle. They must be confirmed with the researcher and recorded before any
# evaluation run, then treated as fixed for the whole study.

# Fixed dispatch-handling overhead added to travel time when computing ATBP. [IMPL]
COORDINATION_OVERHEAD_MIN: int = 5

# Length-of-stay distribution shape and per-bed-type means (minutes). [IMPL]
LOS_DISTRIBUTION: str = "exponential"
LOS_MEAN_MINUTES: Mapping[BedType, int] = {
    BedType.GENERAL: 2880,  # 48 h
    BedType.ICU: 5760,  # 96 h
    BedType.MATERNITY_SPECIALIST: 2160,  # 36 h
}

# Greater Accra bounding box for sampling synthetic patient coordinates and for the
# distance-matrix grid: (lat_min, lat_max, lon_min, lon_max). [IMPL]
GA_BBOX: tuple[float, float, float, float] = (5.45, 5.95, -0.45, 0.25)

# Global RNG seed; every simulation run records the seed it actually used. [IMPL]
RANDOM_SEED: int = 20260617

# Resolution of the precomputed distance-matrix grid over GA_BBOX (rows x cols of patient
# sample points). The matrix has ``rows * cols`` nodes x 24 facilities; each simulated
# patient snaps to its nearest node (docs/07 §3). Larger = finer spatial resolution but
# more one-time build cost (grid x facilities maps-API calls, or Haversine if no key). [IMPL]
DISTANCE_MATRIX_GRID_SIZE: tuple[int, int] = (12, 12)

# Offset added to a session's ``random_seed`` to seed the *independent* length-of-stay RNG
# stream, kept separate from the event-generation stream. Separate streams (common random
# numbers) keep the generated event sequence identical across algorithm configurations at a
# given seed, which is what makes the paired statistical comparison valid (docs/07 §7). [IMPL]
LOS_RANDOM_STREAM_OFFSET: int = 1_000_003


# ---------------------------------------------------------------------------
# [LEGACY — superseded, still in use until Increment 5] Statistical analysis
# ---------------------------------------------------------------------------
# This constant is NOT current docs/09 §9 any more (the doc was rewritten — §9 is now
# "Reservation and notification", added below). It stays here, unrenumbered, only because
# app/analysis/statistics.py (the discrete-event-era hypothesis-testing module) still reads
# it; docs/08 §3 and docs/AGENTS.md §3 now explicitly forbid this kind of analysis over the
# case set ("Do not compute p-values, t-tests or Cohen's d"). Removed when Increment 5
# replaces app/analysis/ and app/simulation/ with the deterministic scenario runner.
SIGNIFICANCE_ALPHA: float = 0.05


# ---------------------------------------------------------------------------
# 9. Reservation and notification (docs/09-parameters.md §9, thesis §3.6.6)
# ---------------------------------------------------------------------------
# None of these four are thesis-specified numbers; they are implementation defaults
# recorded here (not hardcoded in domain/reservation/ or domain/notify/) per docs/09 §9.

# Minutes added to ETA before an unconfirmed reservation expires (docs/01 §7, FR10).
RESERVATION_GRACE_MIN: int = 15

# How often the expiry sweeper checks for reservations past expires_at (docs/01 §7).
SWEEPER_INTERVAL_SEC: int = 60

# Notification channel used for facility confirmation (docs/02 §3.7, FR19).
SMS_CHANNEL: str = "sms"

# Gateway retries before a notification is recorded as delivery-failed (docs/02 §3.7).
SMS_RETRY_ATTEMPTS: int = 2


# ---------------------------------------------------------------------------
# 10. Authentication and access control (docs/09 §10, thesis §3.6.5) [IMPL]
# ---------------------------------------------------------------------------
# None of these four are thesis-specified numbers; they are standard, defensible defaults
# for a JWT + argon2id scheme and are recorded here (not hardcoded in app/security/) so a
# future change is a one-line, auditable edit.

ACCESS_TOKEN_TTL_MIN: int = 30
REFRESH_TOKEN_TTL_DAYS: int = 7
PASSWORD_HASH: str = "argon2id"
MIN_PASSWORD_LENGTH: int = 12


# ---------------------------------------------------------------------------
# 11. Mobile / sync (docs/09 §11, thesis §3.9-3.10)
# ---------------------------------------------------------------------------

# Default interval at which the mobile app refreshes its read-only facility cache.
BACKGROUND_SYNC_INTERVAL_MINUTES: int = 15


# ---------------------------------------------------------------------------
# 12. Validation rules to assert on config load (docs/09-parameters.md §12)
# ---------------------------------------------------------------------------


def _validate_capability_in_range(matrix: Mapping[Urgency, Mapping[Tier, float]]) -> None:
    """Rule 3: every capability-match value must lie in [0, 1]."""
    for urgency, row in matrix.items():
        for tier, value in row.items():
            if not 0.0 <= value <= 1.0:
                raise ParameterValidationError(
                    f"capability[{urgency}][{tier}] = {value!r} is outside [0, 1]"
                )


def _validate_radius_monotonic(radii: Mapping[Urgency, int]) -> None:
    """Rule 4: R(critical) <= R(urgent) <= R(standard).

    A more urgent patient must never be given a wider reach than a less urgent one.
    """
    if not radii[Urgency.CRITICAL] <= radii[Urgency.URGENT] <= radii[Urgency.STANDARD]:
        raise ParameterValidationError(
            "radius must satisfy R(critical) <= R(urgent) <= R(standard), got "
            f"{radii[Urgency.CRITICAL]}, {radii[Urgency.URGENT]}, {radii[Urgency.STANDARD]}"
        )


def _validate_occupancy_scenarios(scenarios: tuple[float, ...]) -> None:
    """Rule 5: the occupancy scenarios are exactly {0.75, 0.90, 1.00}."""
    if set(scenarios) != {0.75, 0.90, 1.00}:
        raise ParameterValidationError(
            f"occupancy scenarios must be exactly {{0.75, 0.90, 1.00}}, got {scenarios!r}"
        )


def _validate_distribution(distribution: Mapping[Any, float], label: str) -> None:
    """Rule 6: a probability distribution's values must sum to 1.0 (±SUM_TOLERANCE)."""
    total = sum(distribution.values())
    if abs(total - 1.0) > SUM_TOLERANCE:
        raise ParameterValidationError(f"{label} distribution must sum to 1.0, got {total!r}")


def validate_parameters() -> None:
    """Run every docs/09 §12 load-time check; raise on the first violation.

    Rules 1-2 (weight rows sum to 1.0) are already enforced by ``WeightVector`` at
    construction, so this function covers the remaining rules 3-6. It is invoked once at
    import (below) so a malformed configuration can never reach a simulation run.
    """
    _validate_capability_in_range(CAPABILITY_MATRIX)
    _validate_radius_monotonic(RADIUS_MINUTES)
    _validate_occupancy_scenarios(OCCUPANCY_SCENARIOS)
    _validate_distribution(URGENCY_DISTRIBUTION, "urgency")
    _validate_distribution(BED_TYPE_DISTRIBUTION, "bed-type")


# Fail fast at import: an invalid parameter set must never be loadable.
validate_parameters()
