import { apiFetch } from "@/lib/api-client";
import type {
  InboundReservation,
  ReservationRead,
  RevokeReservationRequest,
} from "@/lib/types";

// The reservation lifecycle actions a facility-staff account may take from the inbound
// queue (backend/app/api/routes/allocations.py) — acknowledge (FR20, advisory) and revoke
// (FR24-27, releases the bed and notifies the dispatcher). Arrival is deliberately not here:
// only the dispatcher who submitted the request records it (FR22).

export function listInboundReservations(): Promise<InboundReservation[]> {
  return apiFetch<InboundReservation[]>("/allocations/inbound");
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
