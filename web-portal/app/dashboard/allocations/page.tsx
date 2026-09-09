"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listAllocationsOverview } from "@/lib/api/allocations";
import { ApiError } from "@/lib/api-client";
import {
  ALGORITHM_LABELS,
  ALLOCATION_STATUS_CLASSES,
  ALLOCATION_STATUS_LABELS,
  BED_TYPE_LABELS,
  URGENCY_LABELS,
} from "@/lib/labels";
import type { AllocationStatus } from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const STATUSES: AllocationStatus[] = [
  "pending",
  "confirmed",
  "arrived",
  "escalated",
  "expired",
  "refused",
  "revoked",
];
const ALL_STATUSES = "all" as const;
const STATUS_ITEMS = {
  [ALL_STATUSES]: "All statuses",
  ...Object.fromEntries(STATUSES.map((s) => [s, ALLOCATION_STATUS_LABELS[s]])),
};

/**
 * System-administrator oversight (role/permission audit Task 2) — every facility's
 * allocations in one place, newest first. Deliberately READ-ONLY: no action of any kind
 * appears on this page. That isn't a UI choice being enforced by convention — the backend
 * grants system_administrator only `allocation_overview:read:all`; no write permission on
 * that resource exists anywhere, so acknowledge/revoke/refuse/arrive would 403 even if a
 * button called them. Nothing here is wired to try.
 */
export default function AllocationsOverviewPage() {
  const [status, setStatus] = useState<AllocationStatus | typeof ALL_STATUSES>(ALL_STATUSES);

  const query = useQuery({
    queryKey: ["allocations-overview", status],
    queryFn: () =>
      listAllocationsOverview(status === ALL_STATUSES ? {} : { status }),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Allocations</h1>
        <p className="text-sm text-muted-foreground">
          Every current allocation across every facility, newest first — read-only oversight.
        </p>
      </div>

      <Field className="w-auto">
        <FieldLabel htmlFor="status-filter">Status</FieldLabel>
        <Select items={STATUS_ITEMS} value={status} onValueChange={(v) => setStatus(v as typeof status)}>
          <SelectTrigger id="status-filter" className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUSES}>All statuses</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {ALLOCATION_STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Card>
        <CardContent className="px-0">
          {query.isLoading ? (
            <div className="px-4">
              <Skeleton className="h-32 w-full" />
            </div>
          ) : query.error ? (
            <div className="px-4 text-sm text-destructive">
              {query.error instanceof ApiError
                ? query.error.message
                : "Failed to load allocations."}
            </div>
          ) : !query.data || query.data.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No allocations</EmptyTitle>
                <EmptyDescription>Nothing matches this filter yet.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Facility</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Urgency</TableHead>
                  <TableHead>Bed type</TableHead>
                  <TableHead>ETA</TableHead>
                  <TableHead>Algorithm</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.map((row) => {
                  const statusClasses = ALLOCATION_STATUS_CLASSES[row.status];
                  return (
                    <TableRow key={row.id}>
                      <TableCell className="whitespace-nowrap font-mono text-xs">
                        {new Date(row.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm">
                        {row.facility_name ?? (
                          <span className="text-muted-foreground">— (escalated)</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={`${statusClasses.bg} ${statusClasses.text}`}>
                          {ALLOCATION_STATUS_LABELS[row.status]}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {row.urgency ? URGENCY_LABELS[row.urgency] : "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {BED_TYPE_LABELS[row.required_bed_type]}
                      </TableCell>
                      <TableCell className="font-mono text-sm tabular-nums">
                        {row.eta_minutes != null ? `${row.eta_minutes.toFixed(1)} min` : "—"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {ALGORITHM_LABELS[row.algorithm_used]}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
