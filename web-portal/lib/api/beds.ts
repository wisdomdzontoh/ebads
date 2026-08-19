import { apiFetch } from "@/lib/api-client";
import type { BedCountUpdate, Facility } from "@/lib/types";

export function updateBedCount(
  facilityId: string,
  payload: BedCountUpdate
): Promise<Facility> {
  return apiFetch<Facility>(`/facilities/${facilityId}/beds`, {
    method: "PATCH",
    body: payload,
  });
}
