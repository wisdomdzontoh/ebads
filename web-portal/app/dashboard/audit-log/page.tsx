"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listAuditLog } from "@/lib/api/audit";
import { listUsers } from "@/lib/api/users";
import { ApiError } from "@/lib/api-client";

import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function AuditLogPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const emailById = useMemo(() => {
    const map = new Map<string, string>();
    for (const user of usersQuery.data ?? []) {
      map.set(user.id, user.email);
    }
    return map;
  }, [usersQuery.data]);

  const auditQuery = useQuery({
    queryKey: ["audit-log", from, to],
    queryFn: () =>
      listAuditLog({
        from: from ? new Date(from).toISOString() : undefined,
        to: to ? new Date(to).toISOString() : undefined,
      }),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every recorded mutation across the system, newest first.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field className="w-auto">
          <FieldLabel htmlFor="from">From</FieldLabel>
          <Input
            id="from"
            type="datetime-local"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </Field>
        <Field className="w-auto">
          <FieldLabel htmlFor="to">To</FieldLabel>
          <Input
            id="to"
            type="datetime-local"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </Field>
      </div>

      <Card>
        <CardContent className="px-0">
          {auditQuery.isLoading ? (
            <div className="px-4">
              <Skeleton className="h-32 w-full" />
            </div>
          ) : auditQuery.error ? (
            <div className="px-4 text-sm text-destructive">
              {auditQuery.error instanceof ApiError
                ? auditQuery.error.message
                : "Failed to load the audit log."}
            </div>
          ) : !auditQuery.data || auditQuery.data.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No entries</EmptyTitle>
                <EmptyDescription>
                  Nothing was recorded in this time range.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auditQuery.data.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap font-mono text-xs">
                      {new Date(entry.logged_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-sm">
                      {entry.user_id ? (emailById.get(entry.user_id) ?? entry.user_id) : "system"}
                    </TableCell>
                    <TableCell className="text-sm">{entry.action}</TableCell>
                    <TableCell className="text-sm">
                      {entry.entity}
                      <span className="ml-1 font-mono text-xs text-muted-foreground">
                        {entry.entity_id}
                      </span>
                    </TableCell>
                    <TableCell
                      className="max-w-xs truncate font-mono text-xs text-muted-foreground"
                      title={JSON.stringify(entry.detail)}
                    >
                      {JSON.stringify(entry.detail)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
