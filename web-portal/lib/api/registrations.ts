import { apiFetch } from "@/lib/api-client";
import type {
  ApprovalResult,
  FacilityRequest,
  FacilityRequestApprove,
  FacilityRequestReject,
  FacilityRequestStatus,
} from "@/lib/types";

export function listRegistrations(
  status?: FacilityRequestStatus
): Promise<FacilityRequest[]> {
  const query = status ? `?status=${status}` : "";
  return apiFetch<FacilityRequest[]>(`/registrations${query}`);
}

export function approveRegistration(
  id: string,
  payload: FacilityRequestApprove
): Promise<ApprovalResult> {
  return apiFetch<ApprovalResult>(`/registrations/${id}/approve`, {
    method: "POST",
    body: payload,
  });
}

export function rejectRegistration(
  id: string,
  payload: FacilityRequestReject
): Promise<FacilityRequest> {
  return apiFetch<FacilityRequest>(`/registrations/${id}/reject`, {
    method: "POST",
    body: payload,
  });
}
