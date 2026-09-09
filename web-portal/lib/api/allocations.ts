import { apiFetch } from "@/lib/api-client";
import type {
  AllocationOverviewRead,
  AllocationStatus,
  InboundReservation,
  ReservationRead,
  RevokeReservationRequest,
} from "@/lib/types";

// The reservation lifecycle actions a facility-staff (or, as of the role/permission audit,
// facility-administrator — same allocation:write:own_facility grant) account may take from
// the inbound queue (backend/app/api/routes/allocations.py) — acknowledge (FR20, advisory)
// and revoke (FR24-27, releases the bed and notifies the dispatcher). Arrival is deliberately
// not here: only the dispatcher who submitted the request records it (FR22).

export function listInboundReservations(): Promise<InboundReservation[]> {
  return apiFetch<InboundReservation[]>("/allocations/inbound");
}

export interface AllocationOverviewFilter {
  status?: AllocationStatus;
  from?: string;
  to?: string;
}

// GET /allocations/overview (system_administrator only, allocation_overview:read:all) —
// every facility's allocations, read-only. No corresponding write function exists here on
// purpose: this resource has no write permission anywhere in the backend (role/permission
// audit Task 2), so there is nothing for a mutation call to even target.
export function listAllocationsOverview(
  filter: AllocationOverviewFilter = {}
): Promise<AllocationOverviewRead[]> {
  const params = new URLSearchParams();
  if (filter.status) params.set("status", filter.status);
  if (filter.from) params.set("from", filter.from);
  if (filter.to) params.set("to", filter.to);
  const query = params.toString();
  return apiFetch<AllocationOverviewRead[]>(`/allocations/overview${query ? `?${query}` : ""}`);
}

export function acknowledgeReservation(allocationId: string): Promise<ReservationRead> {
  return apiFetch<ReservationRead>(`/allocations/${allocationId}/acknowledge`, {
    method: "POST",
  });
}

export function revokeReservation(
  allocationId: string,
  payload: RevokeReservationRequest
): Promise<void> {
  return apiFetch<void>(`/allocations/${allocationId}/revoke`, {
    method: "POST",
    body: payload,
  });
}
