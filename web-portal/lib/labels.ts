// Human-readable labels for backend/app/parameters.py enums, kept in one place so every
// view spells the same enum value the same way.
import type {
  AlgorithmName,
  AllocationStatus,
  BedType,
  DataSource,
  FacilityRequestStatus,
  Role,
  Tier,
  Urgency,
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

// Triage urgency (docs/09 §1-2) — color is never decorative here, it is the same semantic
// signal the mobile app's design system defines (mobile/src/screens/dispatch/constants.ts,
// DESIGN.md "Semantic Urgency"), wired into app/globals.css as the critical/urgent/standard
// tokens so both clients read as one product.
export const URGENCY_LABELS: Record<Urgency, string> = {
  critical: "Critical",
  urgent: "Urgent",
  standard: "Standard",
};

// Tailwind utility classes reading the matching --color-critical/-urgent/-standard tokens.
// `border` is deliberately the left-edge-scoped utility (not the bare color) so it composes
// with a literal `border-l-4` without depending on tailwind-merge's cross-side resolution —
// it overrides only the left edge, leaving the card's own neutral border on the other three.
export const URGENCY_CLASSES: Record<Urgency, { text: string; bg: string; border: string }> = {
  critical: {
    text: "text-critical",
    bg: "bg-critical-tint",
    border: "border-l-critical/60",
  },
  urgent: {
    text: "text-urgent",
    bg: "bg-urgent-tint",
    border: "border-l-urgent/60",
  },
  standard: {
    text: "text-standard",
    bg: "bg-standard-tint",
    border: "border-l-standard/60",
  },
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

export const ALLOCATION_STATUS_LABELS: Record<AllocationStatus, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  arrived: "Arrived",
  expired: "Expired",
  refused: "Refused",
  escalated: "Escalated",
  revoked: "Revoked",
};

// Tailwind utility classes reading the same critical/urgent/standard tokens
// URGENCY_CLASSES above uses — arrived/confirmed read as healthy, revoked/refused/expired as
// a problem, escalated as needing attention, pending as neutral. Purely descriptive on the
// read-only allocation overview (role/permission audit Task 2) — never a control.
export const ALLOCATION_STATUS_CLASSES: Record<AllocationStatus, { text: string; bg: string }> = {
  pending: { text: "text-muted-foreground", bg: "bg-muted" },
  confirmed: { text: "text-standard", bg: "bg-standard-tint" },
  arrived: { text: "text-standard", bg: "bg-standard-tint" },
  escalated: { text: "text-urgent", bg: "bg-urgent-tint" },
  expired: { text: "text-critical", bg: "bg-critical-tint" },
  refused: { text: "text-critical", bg: "bg-critical-tint" },
  revoked: { text: "text-critical", bg: "bg-critical-tint" },
};

export const ALGORITHM_LABELS: Record<AlgorithmName, string> = {
  greedy: "Greedy",
  weighted: "Weighted",
  urgency_adaptive: "Urgency-adaptive",
};

// Backend/app/parameters.py MIN_PASSWORD_LENGTH — mirrored so the form rejects a too-short
// password before a round trip; the backend (app/security/passwords.py) remains the real
// enforcement point.
export const MIN_PASSWORD_LENGTH = 12;
