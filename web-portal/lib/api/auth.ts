import { apiFetch } from "@/lib/api-client";

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export function changePassword(payload: ChangePasswordRequest): Promise<void> {
  return apiFetch<void>("/auth/password", { method: "PATCH", body: payload });
}
