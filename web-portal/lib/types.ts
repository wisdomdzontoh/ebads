// Mirrors backend/app/parameters.py and backend/app/api/schemas/ — keep field names and
// enum values exact so payloads need no translation layer (docs/EBADS_PRD.md §10).

export type Role =
  | "system_administrator"
  | "facility_administrator"
  | "facility_staff"
  | "dispatcher";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  role: Role;
  facility_id: string | null;
}

export interface AccessTokenResponse {
  access_token: string;
}

// FastAPI's default error shape: `detail` is a string for a raised HTTPException, or an
// array of Pydantic validation errors for a 422.
export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

export type Tier = "tertiary" | "secondary" | "primary";

export type BedType = "general" | "icu" | "maternity_specialist";

// null on a facility/request = manual maintenance (docs/02 §3.1); MANUAL itself is only
// ever used by the (unbuilt) emr_adapter history table, never as a live facility value.
export type DataSource = "manual" | "ghs_data" | "fhir_r4" | "rest_polling";

export type UserStatus = "active" | "suspended";

export type FacilityRequestStatus = "pending" | "approved" | "rejected";

// --- facilities -------------------------------------------------------------------------

export interface BedCount {
  bed_type: BedType;
  available: number;
  capacity: number;
  version: number;
  updated_at: string;
  updated_by: string | null;
}

export interface Facility {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  tier: Tier;
  supported_bed_types: BedType[];
  contact_phone: string;
  active_data_source: DataSource | null;
  created_at: string;
  updated_at: string;
  bed_counts: BedCount[];
}

// Body of PUT /facilities/{id} — a full replacement of static attributes, not a partial
// patch (backend/app/api/schemas/facility.py::FacilityUpdate).
export interface FacilityUpdate {
  name: string;
  latitude: number;
  longitude: number;
  tier: Tier;
  supported_bed_types: BedType[];
  contact_phone: string;
  active_data_source?: DataSource | null;
}

// Body of PATCH /facilities/{id}/beds — upserts one bed-type's counts (no client-supplied
// version: this is the human-correction path, distinct from the CAS reservation protocol).
export interface BedCountUpdate {
  bed_type: BedType;
  available: number;
  capacity: number;
}

// --- registrations ------------------------------------------------------------------------

export interface FacilityRequest {
  id: string;
  facility_name: string;
  ghs_code: string;
  tier: Tier;
  contact_email: string;
  contact_phone: string;
  status: FacilityRequestStatus;
  reviewed_by: string | null;
  rejection_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface FacilityRequestApprove {
  latitude: number;
  longitude: number;
  supported_bed_types: BedType[];
  active_data_source?: DataSource | null;
  initial_admin_email: string;
  initial_admin_password: string;
}

export interface FacilityRequestReject {
  reason: string;
}

export interface ApprovalResult {
  facility_id: string;
  facility_name: string;
  admin_user_id: string;
  admin_email: string;
}

// --- users --------------------------------------------------------------------------------

export interface UserCreate {
  email: string;
  password: string;
  role: Role;
  facility_id?: string | null;
}

export interface User {
  id: string;
  email: string;
  role: Role;
  facility_id: string | null;
  status: UserStatus;
  created_at: string;
  last_login_at: string | null;
}

// --- audit log ------------------------------------------------------------------------------

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  entity: string;
  entity_id: string;
  detail: Record<string, unknown>;
  logged_at: string;
}
