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

/** Allocated allocation response (docs/04 §4). */
export interface AllocatedResponse {
  id: string;
  status: 'allocated';
  recommended_facility: RecommendedFacility;
  algorithm_used: AlgorithmName;
  weight_vector: WeightVector | null;
  capability_match: number;
  candidates_evaluated: number;
  selection_reason: string;
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
