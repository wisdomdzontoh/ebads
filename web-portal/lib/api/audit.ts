import { apiFetch } from "@/lib/api-client";
import type { AuditLogEntry } from "@/lib/types";

export interface AuditLogFilter {
  from?: string;
  to?: string;
}

export function listAuditLog(filter: AuditLogFilter = {}): Promise<AuditLogEntry[]> {
  const params = new URLSearchParams();
  if (filter.from) params.set("from", filter.from);
  if (filter.to) params.set("to", filter.to);
  const query = params.toString();
  return apiFetch<AuditLogEntry[]>(`/audit-log${query ? `?${query}` : ""}`);
}
