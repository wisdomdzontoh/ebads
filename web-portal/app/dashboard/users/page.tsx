"use client";

import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listFacilities } from "@/lib/api/facilities";
import { listUsers } from "@/lib/api/users";
import { ApiError } from "@/lib/api-client";
import { ROLE_LABELS, USER_STATUS_LABELS } from "@/lib/labels";

import { Badge, badgeVariants } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { VariantProps } from "class-variance-authority";
import type { UserStatus } from "@/lib/types";

import { CreateUserDialog } from "./create-user-dialog";

type BadgeVariant = VariantProps<typeof badgeVariants>["variant"];

const STATUS_BADGE_VARIANT: Record<UserStatus, BadgeVariant> = {
  active: "default",
  suspended: "destructive",
};

export default function UsersPage() {
  const queryClient = useQueryClient();

  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const facilitiesQuery = useQuery({
    queryKey: ["facilities"],
    queryFn: listFacilities,
    staleTime: 60_000,
  });

  const facilityNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const facility of facilitiesQuery.data ?? []) {
      map.set(facility.id, facility.name);
    }
    return map;
  }, [facilitiesQuery.data]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Users</h1>
          <p className="text-sm text-muted-foreground">
            Every account across the system, and where it&apos;s scoped.
          </p>
        </div>
        <CreateUserDialog onSuccess={invalidate} />
      </div>

      <Card>
        <CardContent className="px-0">
          {usersQuery.isLoading ? (
            <div className="px-4">
              <Skeleton className="h-32 w-full" />
            </div>
          ) : usersQuery.error ? (
            <div className="px-4 text-sm text-destructive">
              {usersQuery.error instanceof ApiError
                ? usersQuery.error.message
                : "Failed to load users."}
            </div>
          ) : !usersQuery.data || usersQuery.data.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No users yet</EmptyTitle>
                <EmptyDescription>Create the first account above.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Facility</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Last login</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usersQuery.data.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.email}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{ROLE_LABELS[user.role]}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {user.facility_id
                        ? (facilityNameById.get(user.facility_id) ?? user.facility_id)
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_BADGE_VARIANT[user.status]}>
                        {USER_STATUS_LABELS[user.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(user.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {user.last_login_at
                        ? new Date(user.last_login_at).toLocaleString()
                        : "Never"}
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
