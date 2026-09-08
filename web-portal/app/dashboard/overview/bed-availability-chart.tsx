"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import type { Facility } from "@/lib/types";
import { BED_TYPE_LABELS } from "@/lib/labels";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

const BED_CHART: ChartConfig = {
  available: { label: "Available", color: "var(--chart-3)" },
  occupied: { label: "Occupied", color: "var(--chart-2)" },
};

/** Stacked available/occupied bars, one per supported bed type — shared by the
 * facility_administrator and facility_staff Overview dashboards (both manage the same
 * facility's bed_state, docs/02 §2.3). */
export function BedAvailabilityChart({ facility }: { facility: Facility }) {
  const data = useMemo(
    () =>
      facility.supported_bed_types.map((bedType) => {
        const count = facility.bed_counts.find((bc) => bc.bed_type === bedType);
        const capacity = count?.capacity ?? 0;
        const available = count?.available ?? 0;
        return {
          bedType,
          label: BED_TYPE_LABELS[bedType],
          available,
          occupied: Math.max(0, capacity - available),
        };
      }),
    [facility],
  );

  return (
    <ChartContainer config={BED_CHART} className="aspect-auto h-[240px] w-full">
      <BarChart data={data} margin={{ left: 0, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis tickLine={false} axisLine={false} width={28} allowDecimals={false} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="available" stackId="beds" fill="var(--color-available)" />
        <Bar dataKey="occupied" stackId="beds" fill="var(--color-occupied)" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ChartContainer>
  );
}
