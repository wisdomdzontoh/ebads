import { apiFetch } from "@/lib/api-client";
import type { User, UserCreate } from "@/lib/types";

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>("/users");
}

export function createUser(payload: UserCreate): Promise<User> {
  return apiFetch<User>("/users", { method: "POST", body: payload });
}
