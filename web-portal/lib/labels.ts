// Human-readable labels for backend/app/parameters.py enums, kept in one place so every
// view spells the same enum value the same way.
import type {
  BedType,
  DataSource,
  FacilityRequestStatus,
  Role,
  Tier,
  UserStatus,
} from "./types";

export const ROLE_LABELS: Record<Role, string> = {
  system_administrator: "System Administrator",
  facility_administrator: "Facility Administrator",
  facility_staff: "Facility Staff",
  dispatcher: "Dispatcher",
};

export const TIER_LABELS: Record<Tier, string> = {
  tertiary: "Tertiary",
  secondary: "Secondary",
  primary: "Primary",
};

export const BED_TYPE_LABELS: Record<BedType, string> = {
  general: "General",
  icu: "ICU",
  maternity_specialist: "Maternity / Specialist",
};

// "manual" is intentionally omitted — a facility's active_data_source is only ever one of
// the three live adapters or null (null itself means manual maintenance, docs/02 §3.1).
export const DATA_SOURCE_LABELS: Record<Exclude<DataSource, "manual">, string> = {
  ghs_data: "GHS Data",
  fhir_r4: "FHIR R4",
  rest_polling: "REST Polling",
};

export const FACILITY_REQUEST_STATUS_LABELS: Record<FacilityRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export const USER_STATUS_LABELS: Record<UserStatus, string> = {
  active: "Active",
  suspended: "Suspended",
};

// Backend/app/parameters.py MIN_PASSWORD_LENGTH — mirrored so the form rejects a too-short
// password before a round trip; the backend (app/security/passwords.py) remains the real
// enforcement point.
export const MIN_PASSWORD_LENGTH = 12;
