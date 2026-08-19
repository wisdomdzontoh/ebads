import { apiFetch } from "@/lib/api-client";
import type { Facility } from "@/lib/types";

export function listFacilities(): Promise<Facility[]> {
  return apiFetch<Facility[]>("/facilities");
}
