import { apiFetch } from "@/lib/api-client";
import type { Facility, FacilityUpdate } from "@/lib/types";

export function listFacilities(): Promise<Facility[]> {
  return apiFetch<Facility[]>("/facilities");
}

export function updateFacility(id: string, payload: FacilityUpdate): Promise<Facility> {
  return apiFetch<Facility>(`/facilities/${id}`, { method: "PUT", body: payload });
}
