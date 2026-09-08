"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart } from "recharts";

import { useAuth } from "@/components/auth-provider";
import { listInboundReservations } from "@/lib/api/allocations";
import { listFacilities } from "@/lib/api/facilities";
import { URGENCY_LABELS } from "@/lib/labels";
import type { Urgency } from "@/lib/types";

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

const URGENCIES: Urgency[] = ["critical", "urgent", "standard"];

const URGENCY_CHART: ChartConfig = {
  critical: { label: URGENCY_LABELS.critical, color: "var(--color-critical)" },
  urgent: { label: URGENCY_LABELS.urgent, color: "var(--color-urgent)" },
  standard: { label: URGENCY_LABELS.standard, color: "var(--color-standard)" },
};

/** Facility Staff's Overview — what's incoming right now, and this facility's own bed
 * availability (facility_staff holds bed_state:write:own_facility too, same as
 * facility_administrator). Same data the Incoming allocations/Beds pages already show. */
export function FacilityStaffOverview() {
  const { user } = useAuth();
  const facilitiesQuery = useQuery({ queryKey: ["facilities"], queryFn: listFacilities });
  const inboundQuery = useQuery({
    queryKey: ["inbound-reservations"],
    queryFn: listInboundReservations,
  });

  const facility = facilitiesQuery.data?.find((f) => f.id === user?.facilityId) ?? null;
  const reservations = useMemo(() => inboundQuery.data ?? [], [inboundQuery.data]);

  const urgencyData = useMemo(
    () =>
      URGENCIES.map((urgency) => ({
        urgency,
        label: URGENCY_LABELS[urgency],
        count: reservations.filter((r) => r.urgency === urgency).length,
        fill: `var(--color-${urgency})`,
      })).filter((row) => row.count > 0),
    [reservations],
  );

  const pendingCount = reservations.filter((r) => !r.acknowledged_at).length;
  const avgEta = useMemo(() => {
    const known = reservations.map((r) => r.eta_minutes).filter((v): v is number => v != null);
    if (known.length === 0) return null;
    return Math.round(known.reduce((s, v) => s + v, 0) / known.length);
  }, [reservations]);

  if (facilitiesQuery.isLoading || inboundQuery.isLoading) {
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
        <KpiStat
          label="Incoming reservations"
          value={reservations.length}
          tone={reservations.length > 0 ? "urgent" : "default"}
        />
        <KpiStat
          label="Awaiting acknowledgement"
          value={pendingCount}
          tone={pendingCount > 0 ? "critical" : "standard"}
        />
        <KpiStat label="Average ETA" value={avgEta != null ? `${avgEta}m` : "—"} />
        {facility && (
          <KpiStat
            label="Beds available"
            value={facility.bed_counts.reduce((s, bc) => s + bc.available, 0)}
          />
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Incoming reservations by urgency</CardTitle>
            <CardDescription>Currently held for your facility.</CardDescription>
          </CardHeader>
          <CardContent className="flex items-center justify-center">
            {urgencyData.length === 0 ? (
              <p className="py-8 text-sm text-muted-foreground">Nothing incoming right now.</p>
            ) : (
              <ChartContainer config={URGENCY_CHART} className="aspect-auto h-[220px] w-full">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent hideLabel nameKey="urgency" />} />
                  <Pie
                    data={urgencyData}
                    dataKey="count"
                    nameKey="urgency"
                    innerRadius={48}
                    outerRadius={80}
                    strokeWidth={2}
                  >
                    {urgencyData.map((row) => (
                      <Cell key={row.urgency} fill={row.fill} />
                    ))}
                  </Pie>
                  <ChartLegend content={<ChartLegendContent nameKey="urgency" />} />
                </PieChart>
              </ChartContainer>
            )}
          </CardContent>
        </Card>

        {facility && (
          <Card>
            <CardHeader>
              <CardTitle>Bed availability by type</CardTitle>
              <CardDescription>{facility.name} — available vs. occupied.</CardDescription>
            </CardHeader>
            <CardContent>
              <BedAvailabilityChart facility={facility} />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
