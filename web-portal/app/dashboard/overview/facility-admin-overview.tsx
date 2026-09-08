"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart } from "recharts";

import { useAuth } from "@/components/auth-provider";
import { listFacilities } from "@/lib/api/facilities";
import { listUsers } from "@/lib/api/users";
import { ROLE_LABELS } from "@/lib/labels";
import type { Role } from "@/lib/types";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { KpiStat } from "@/components/ui/kpi-stat";
import { Skeleton } from "@/components/ui/skeleton";

import { BedAvailabilityChart } from "./bed-availability-chart";

const STAFF_ROLES: Role[] = ["facility_administrator", "facility_staff"];

const STAFF_CHART: ChartConfig = {
  facility_administrator: { label: ROLE_LABELS.facility_administrator, color: "var(--chart-1)" },
  facility_staff: { label: ROLE_LABELS.facility_staff, color: "var(--chart-3)" },
};

/** Facility Administrator's Overview — this facility's own bed availability and staffing, at
 * a glance. Same data the Beds/Users pages already show, summarized. */
export function FacilityAdminOverview() {
  const { user } = useAuth();
  const facilitiesQuery = useQuery({ queryKey: ["facilities"], queryFn: listFacilities });
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });

  const facility = facilitiesQuery.data?.find((f) => f.id === user?.facilityId) ?? null;
  const staff = (usersQuery.data ?? []).filter((u) => u.facility_id === user?.facilityId);

  const staffData = useMemo(
    () =>
      STAFF_ROLES.map((role) => ({
        role,
        label: ROLE_LABELS[role],
        count: staff.filter((u) => u.role === role).length,
        fill: `var(--color-${role})`,
      })).filter((row) => row.count > 0),
    [staff],
  );

  const totalCapacity = facility?.bed_counts.reduce((s, bc) => s + bc.capacity, 0) ?? 0;
  const totalAvailable = facility?.bed_counts.reduce((s, bc) => s + bc.available, 0) ?? 0;

  if (facilitiesQuery.isLoading || usersQuery.isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (!facility) {
    return (
      <p className="text-sm text-muted-foreground">
        No facility is associated with your account.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiStat label="Bed capacity" value={totalCapacity} />
        <KpiStat
          label="Beds available"
          value={totalAvailable}
          tone={totalAvailable === 0 ? "critical" : totalAvailable < totalCapacity * 0.25 ? "urgent" : "standard"}
        />
        <KpiStat label="Bed types" value={facility.supported_bed_types.length} />
        <KpiStat label="Staff accounts" value={staff.length} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Bed availability by type</CardTitle>
            <CardDescription>{facility.name} — available vs. occupied.</CardDescription>
          </CardHeader>
          <CardContent>
            <BedAvailabilityChart facility={facility} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Staff by role</CardTitle>
            <CardDescription>Accounts at {facility.name}.</CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            {staffData.length === 0 ? (
              <p className="py-8 text-sm text-muted-foreground">No staff accounts yet.</p>
            ) : (
              <ChartContainer config={STAFF_CHART} className="aspect-auto h-[240px] w-full">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="role" />} />
                  <Pie
                    data={staffData}
                    dataKey="count"
                    nameKey="role"
                    innerRadius={48}
                    outerRadius={80}
                    strokeWidth={2}
                  >
                    {staffData.map((row) => (
                      <Cell key={row.role} fill={row.fill} />
                    ))}
                  </Pie>
                  <ChartLegend content={<ChartLegendContent nameKey="role" />} />
                </PieChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
