"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";

import { listAuditLog } from "@/lib/api/audit";
import { listFacilities } from "@/lib/api/facilities";
import { listRegistrations } from "@/lib/api/registrations";
import { listUsers } from "@/lib/api/users";
import { ROLE_LABELS, TIER_LABELS } from "@/lib/labels";
import type { Role, Tier } from "@/lib/types";

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

const AUDIT_WINDOW_DAYS = 14;
const TIERS: Tier[] = ["tertiary", "secondary", "primary"];
const ROLES: Role[] = ["system_administrator", "facility_administrator", "facility_staff", "dispatcher"];

const ROLE_CHART: ChartConfig = {
  system_administrator: { label: ROLE_LABELS.system_administrator, color: "var(--chart-1)" },
  facility_administrator: { label: ROLE_LABELS.facility_administrator, color: "var(--chart-3)" },
  facility_staff: { label: ROLE_LABELS.facility_staff, color: "var(--chart-5)" },
  dispatcher: { label: ROLE_LABELS.dispatcher, color: "var(--chart-6)" },
};

const TIER_CHART: ChartConfig = {
  count: { label: "Facilities", color: "var(--chart-1)" },
};

const ACTIVITY_CHART: ChartConfig = {
  count: { label: "Events", color: "var(--chart-1)" },
};

/** System Administrator's Overview — the whole-system health snapshot: how many facilities
 * and accounts exist, what's waiting on approval, and recent activity volume. Every number
 * comes from the same list endpoints the dedicated pages (Registrations/Users/Audit log)
 * already call — this is a summary of that real data, not a separate invented source. */
export function SystemAdminOverview() {
  const facilitiesQuery = useQuery({ queryKey: ["facilities"], queryFn: listFacilities });
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const registrationsQuery = useQuery({
    queryKey: ["registrations", "all"],
    queryFn: () => listRegistrations(),
  });
  const auditFrom = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - AUDIT_WINDOW_DAYS);
    return d.toISOString();
  }, []);
  const auditQuery = useQuery({
    queryKey: ["audit-log", "overview", auditFrom],
    queryFn: () => listAuditLog({ from: auditFrom }),
  });

  const loading =
    facilitiesQuery.isLoading ||
    usersQuery.isLoading ||
    registrationsQuery.isLoading ||
    auditQuery.isLoading;

  const tierData = useMemo(() => {
    const facilities = facilitiesQuery.data ?? [];
    return TIERS.map((tier) => ({
      tier,
      label: TIER_LABELS[tier],
      count: facilities.filter((f) => f.tier === tier).length,
    }));
  }, [facilitiesQuery.data]);

  const roleData = useMemo(() => {
    const users = usersQuery.data ?? [];
    return ROLES.map((role) => ({
      role,
      label: ROLE_LABELS[role],
      count: users.filter((u) => u.role === role).length,
      fill: `var(--color-${role})`,
    })).filter((row) => row.count > 0);
  }, [usersQuery.data]);

  const pendingRegistrations = useMemo(
    () => (registrationsQuery.data ?? []).filter((r) => r.status === "pending").length,
    [registrationsQuery.data],
  );

  const activityData = useMemo(() => {
    const entries = auditQuery.data ?? [];
    const byDay = new Map<string, number>();
    for (let i = AUDIT_WINDOW_DAYS - 1; i >= 0; i -= 1) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      byDay.set(d.toISOString().slice(0, 10), 0);
    }
    for (const entry of entries) {
      const day = entry.logged_at.slice(0, 10);
      if (byDay.has(day)) byDay.set(day, (byDay.get(day) ?? 0) + 1);
    }
    return Array.from(byDay.entries()).map(([day, count]) => ({
      day: day.slice(5), // MM-DD
      count,
    }));
  }, [auditQuery.data]);

  const totalBeds = useMemo(() => {
    const facilities = facilitiesQuery.data ?? [];
    return facilities.reduce(
      (sum, f) => sum + f.bed_counts.reduce((s, bc) => s + bc.capacity, 0),
      0,
    );
  }, [facilitiesQuery.data]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiStat label="Facilities" value={facilitiesQuery.data?.length ?? 0} />
        <KpiStat
          label="Pending registrations"
          value={pendingRegistrations}
          tone={pendingRegistrations > 0 ? "urgent" : "default"}
          sublabel={pendingRegistrations > 0 ? "Awaiting review" : "All clear"}
        />
        <KpiStat label="User accounts" value={usersQuery.data?.length ?? 0} />
        <KpiStat label="Bed capacity" value={totalBeds} sublabel="across all facilities" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Activity, last {AUDIT_WINDOW_DAYS} days</CardTitle>
            <CardDescription>Audit log events per day, system-wide.</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={ACTIVITY_CHART} className="aspect-auto h-[220px] w-full">
              <LineChart data={activityData} margin={{ left: 0, right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="day"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  interval="preserveStartEnd"
                />
                <YAxis tickLine={false} axisLine={false} width={28} allowDecimals={false} />
                <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="var(--color-count)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Facilities by tier</CardTitle>
            <CardDescription>Registered facilities, grouped by care tier.</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={TIER_CHART} className="aspect-auto h-[220px] w-full">
              <BarChart data={tierData} margin={{ left: 0, right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                <YAxis tickLine={false} axisLine={false} width={28} allowDecimals={false} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="count" fill="var(--color-count)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Users by role</CardTitle>
            <CardDescription>Every account across the system.</CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            {roleData.length === 0 ? (
              <p className="py-8 text-sm text-muted-foreground">No users yet.</p>
            ) : (
              <ChartContainer config={ROLE_CHART} className="aspect-auto h-[220px] w-full">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="role" />} />
                  <Pie
                    data={roleData}
                    dataKey="count"
                    nameKey="role"
                    innerRadius={48}
                    outerRadius={80}
                    strokeWidth={2}
                  >
                    {roleData.map((row) => (
                      <Cell key={row.role} fill={row.fill} />
                    ))}
                  </Pie>
                  <ChartLegend content={<ChartLegendContent nameKey="role" />} />
                </PieChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Registration requests</CardTitle>
            <CardDescription>New-facility requests, by current status.</CardDescription>
          </CardHeader>
          <CardContent>
            {(() => {
              const requests = registrationsQuery.data ?? [];
              const statusData = (["pending", "approved", "rejected"] as const).map((status) => ({
                status,
                label: status[0].toUpperCase() + status.slice(1),
                count: requests.filter((r) => r.status === status).length,
              }));
              return (
                <ChartContainer
                  config={{ count: { label: "Requests", color: "var(--chart-4)" } }}
                  className="aspect-auto h-[220px] w-full"
                >
                  <BarChart data={statusData} layout="vertical" margin={{ left: 8, right: 8 }}>
                    <CartesianGrid horizontal={false} />
                    <XAxis type="number" tickLine={false} axisLine={false} allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      tickLine={false}
                      axisLine={false}
                      width={72}
                    />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="count" fill="var(--color-count)" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ChartContainer>
              );
            })()}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
