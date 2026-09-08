/**
 * API domain types — a faithful mirror of the engine's response shapes (docs/04-api-spec.md).
 *
 * These are the ONLY source of truth the client renders from. The mobile app is a thin client
 * (docs/05 §8): it never computes a recommendation, a score, or a ranking — it deserialises
 * exactly what the engine returns and displays it. Field names and enum spellings match the
 * backend Pydantic schemas one-for-one so a response parses without transformation.
 */

export type Urgency = 'critical' | 'urgent' | 'standard';
export type Tier = 'tertiary' | 'secondary' | 'primary';
export type BedType = 'general' | 'icu' | 'maternity_specialist';
export type AlgorithmName = 'greedy' | 'weighted' | 'urgency_adaptive';
export type DataSource =
  | 'simulation'
  | 'facility_management'
  | 'national_emr'
  | 'hl7_fhir';

// --- auth (docs/09 §10, EBADS_PRD.md §10) ------------------------------------

export type Role = 'system_administrator' | 'facility_administrator' | 'facility_staff' | 'dispatcher';

export interface LoginRequest {
  email: string;
  password: string;
}

/** Body of `POST /auth/login` (backend/app/api/schemas/auth.py::TokenResponse). */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  role: Role;
  facility_id: string | null;
}

export interface AccessTokenResponse {
  access_token: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
}

/** A single bed-type availability row embedded in a facility (docs/02 §2.2). */
export interface BedCount {
  bed_type: BedType;
  available: number;
  capacity: number;
  updated_at: string;
}

/** A registered facility with its live bed counts (`GET /facilities`, docs/04 §3). */
export interface Facility {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  tier: Tier;
  supported_bed_types: BedType[];
  contact_phone: string;
  active_data_source: DataSource;
  created_at: string;
  updated_at: string;
  bed_counts: BedCount[];
}

/** The (w_t, w_b, w_c) weight vector actually applied (docs/03). */
export interface WeightVector {
  w_t: number;
  w_b: number;
  w_c: number;
}

/** Body of `POST /allocations` (docs/04 §4). `urgency` null → engine uses Algorithm 2. */
export interface AllocationRequest {
  patient_lat: number;
  patient_lon: number;
  urgency: Urgency | null;
  required_bed_type: BedType;
  simulation_session_id?: string | null;
}

/** The recommended facility in an allocated response (docs/04 §4). */
export interface RecommendedFacility {
  id: string;
  name: string;
  tier: Tier;
  available_beds: number;
  travel_time_minutes: number;
  is_estimated_travel_time: boolean;
  latitude: number;
  longitude: number;
  contact_phone: string;
}

/** A minimal facility reference used in an escalation fallback (docs/04 §4). */
export interface FacilityBrief {
  id: string;
  name: string;
  travel_time_minutes: number;
  available_beds: number;
}

/** A runner-up from the same scoring pass as the confirmed recommendation — shown for the
 * dispatcher's situational awareness only. Never reserved; nothing here is tappable into a
 * new allocation (docs/05 §8: the client never matches — this is a read-only echo of an
 * already-completed server-side ranking, backend/app/parameters.py::MAX_RANKED_ALTERNATIVES). */
export interface RankedAlternative {
  id: string;
  name: string;
  tier: Tier;
  available_beds: number;
  travel_time_minutes: number;
  is_estimated_travel_time: boolean;
  capability_match: number;
  score: number;
}

/** Allocated allocation response (docs/04 §4).
 *
 * `status` is `'confirmed'` — the reservation-protocol lifecycle value
 * (backend/app/parameters.py::AllocationStatus.CONFIRMED), NOT the pure scoring verdict's own
 * `'allocated'` (a separate, internal-only `Status` enum the API never actually sends). This
 * previously read `'allocated'` here, so `result.status === 'allocated'` was always false and
 * EVERY successful placement rendered as an escalation instead — fixed; see git history if
 * this regresses again. */
export interface AllocatedResponse {
  id: string;
  status: 'confirmed';
  recommended_facility: RecommendedFacility;
  algorithm_used: AlgorithmName;
  weight_vector: WeightVector | null;
  capability_match: number;
  candidates_evaluated: number;
  attempts: number;
  eta_minutes: number;
  selection_reason: string;
  /** Runners-up from the same scoring pass — may be empty (only one candidate existed, or
   * FR9's reservation fall-through exhausted the rest). */
  ranked_alternatives: RankedAlternative[];
}

/** Escalated allocation response (docs/04 §4). */
export interface EscalatedResponse {
  id: string;
  status: 'escalated';
  recommended_facility: null;
  requires_manual_decision: true;
  nearest_within_radius: FacilityBrief | null;
  nearest_available_outside_radius: FacilityBrief | null;
  algorithm_used: AlgorithmName;
  candidates_evaluated: number;
  selection_reason: string;
}

/** The allocation endpoint always returns 200 with one of these two shapes (docs/04 §4). */
export type AllocationResponse = AllocatedResponse | EscalatedResponse;

// --- allocation lifecycle (FR20, FR22, FR24-27, docs/01 §7) ------------------

/** Lifecycle status of one persisted allocation, distinct from the pure ALLOCATED/ESCALATED
 * scoring verdict above — this is what `GET /allocations/{id}` reports as it evolves after
 * confirmation (backend/app/parameters.py::AllocationStatus). */
export type AllocationStatus =
  | 'pending'
  | 'confirmed'
  | 'arrived'
  | 'expired'
  | 'refused'
  | 'escalated'
  // The receiving facility withdrew the reservation before arrival (FR24-27) — this is the
  // one status the app actively watches for on a confirmed allocation, to trigger the
  // revocation-redirect flow.
  | 'revoked';

/** One persisted allocation's full record (`GET /allocations/{id}`, `GET /allocations`,
 * backend/app/api/schemas/allocation.py::AllocationAuditRead) — used to poll a confirmed
 * allocation for a status change (arrival recorded elsewhere, or revoked) since the app has
 * no real push channel from the engine (FR19's SMS/push gateways are log-only, docs/01 §3.6). */
export interface AllocationAuditRead {
  id: string;
  created_at: string;
  patient_lat: number;
  patient_lon: number;
  urgency: Urgency | null;
  required_bed_type: BedType;
  simulation_session_id: string | null;
  algorithm_used: AlgorithmName;
  weight_vector: WeightVector | null;
  selection_reason: string;
  facility_id: string | null;
  travel_time_minutes: number | null;
  is_estimated_travel_time: boolean;
  eta_minutes: number | null;
  capability_match: number | null;
  candidates_evaluated: number;
  attempts: number;
  status: AllocationStatus;
  supersedes_allocation_id: string | null;
  /** The facility's stated reason, only ever non-null when `status === 'revoked'` (FR24-27). */
  revocation_reason: string | null;
}

/** Body of `POST /allocations/{id}/reallocate` — the dispatcher's CURRENT position, not the
 * original incident location (docs/01 §7, FR24-27). */
export interface ReallocateRequest {
  current_lat: number;
  current_lon: number;
}

// --- Simulation (docs/04 §5) ------------------------------------------------

export interface SimulationSessionCreate {
  algorithm_config: AlgorithmName;
  occupancy_scenario: number;
  events_planned: number;
  random_seed: number;
}

export interface SimulationSessionRead {
  id: string;
  algorithm_config: AlgorithmName;
  occupancy_scenario: number;
  events_planned: number;
  random_seed: number;
  created_at: string;
  status: string;
  events_processed: number;
}

export interface RunMetrics {
  atbp: number | null;
  frr: number;
  mcee: number;
  cm: number | null;
  cm_critical: number | null;
  events_total: number;
  events_allocated: number;
  events_escalated: number;
}

export interface RunSummary {
  session_id: string;
  events_processed: number;
  status: string;
  metrics: RunMetrics;
}

export interface StepCandidate {
  facility_id: string;
  travel_time_minutes: number;
  available_beds: number;
  t_hat: number;
  b_hat: number;
  c_hat: number;
  score: number;
}

export interface StepTrace {
  event_index: number;
  candidates: StepCandidate[];
  selected_facility_id: string | null;
  algorithm_used: AlgorithmName;
  weight_vector: WeightVector | null;
  status: 'allocated' | 'escalated';
}
