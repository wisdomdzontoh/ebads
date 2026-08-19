"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listRegistrations } from "@/lib/api/registrations";
import { ApiError } from "@/lib/api-client";
import { FACILITY_REQUEST_STATUS_LABELS, TIER_LABELS } from "@/lib/labels";
import type { FacilityRequest, FacilityRequestStatus } from "@/lib/types";

import { Badge, badgeVariants } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ApproveRegistrationDialog } from "./approve-dialog";
import { RejectRegistrationDialog } from "./reject-dialog";
import type { VariantProps } from "class-variance-authority";

type BadgeVariant = VariantProps<typeof badgeVariants>["variant"];

const TABS: { value: FacilityRequestStatus | "all"; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

const STATUS_BADGE_VARIANT: Record<FacilityRequestStatus, BadgeVariant> = {
  pending: "secondary",
  approved: "default",
  rejected: "destructive",
};

export default function RegistrationsPage() {
  const [tab, setTab] = useState<FacilityRequestStatus | "all">("pending");
  const [approveTarget, setApproveTarget] = useState<FacilityRequest | null>(null);
  const [rejectTarget, setRejectTarget] = useState<FacilityRequest | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["registrations", tab],
    queryFn: () => listRegistrations(tab === "all" ? undefined : tab),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["registrations"] });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Facility registrations</h1>
        <p className="text-sm text-muted-foreground">
          Review submitted facility registrations, and approve or reject each one.
        </p>
      </div>

      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as FacilityRequestStatus | "all")}
      >
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card>
        <CardContent className="px-0">
          {isLoading ? (
            <div className="px-4">
              <Skeleton className="h-32 w-full" />
            </div>
          ) : error ? (
            <div className="px-4 text-sm text-destructive">
              {error instanceof ApiError
                ? error.message
                : "Failed to load registrations."}
            </div>
          ) : !data || data.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No requests</EmptyTitle>
                <EmptyDescription>
                  There are no {tab === "all" ? "" : `${tab} `}registration requests.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Facility</TableHead>
                  <TableHead>GHS code</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-medium">
                      {request.facility_name}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {request.ghs_code}
                    </TableCell>
                    <TableCell>{TIER_LABELS[request.tier]}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span>{request.contact_email}</span>
                        <span className="text-xs text-muted-foreground">
                          {request.contact_phone}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_BADGE_VARIANT[request.status]}>
                        {FACILITY_REQUEST_STATUS_LABELS[request.status]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(request.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {request.status === "pending" ? (
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setRejectTarget(request)}
                          >
                            Reject
                          </Button>
                          <Button size="sm" onClick={() => setApproveTarget(request)}>
                            Approve
                          </Button>
                        </div>
                      ) : request.status === "rejected" && request.rejection_reason ? (
                        <span className="text-xs text-muted-foreground">
                          {request.rejection_reason}
                        </span>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ApproveRegistrationDialog
        request={approveTarget}
        onOpenChange={(open) => !open && setApproveTarget(null)}
        onSuccess={() => {
          setApproveTarget(null);
          invalidate();
        }}
      />
      <RejectRegistrationDialog
        request={rejectTarget}
        onOpenChange={(open) => !open && setRejectTarget(null)}
        onSuccess={() => {
          setRejectTarget(null);
          invalidate();
        }}
      />
    </div>
  );
}
