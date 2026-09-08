import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A single stat tile — the reference design system's `.kpi` card (mono uppercase label, a
 * large tabular-nums figure, optional trailing unit/sublabel). Used across the role-specific
 * Overview dashboards; every value passed in comes from a real API response, never invented.
 */
export function KpiStat({
  label,
  value,
  sublabel,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  sublabel?: string;
  tone?: "default" | "critical" | "urgent" | "standard";
}) {
  return (
    <div className="flex flex-col gap-1.5 rounded-xl border border-border bg-card p-4">
      <span className="font-mono text-[10.5px] font-medium tracking-wider text-muted-foreground uppercase">
        {label}
      </span>
      <span
        className={cn(
          "text-[28px] leading-none font-semibold tracking-tight tabular-nums",
          tone === "critical" && "text-critical",
          tone === "urgent" && "text-urgent",
          tone === "standard" && "text-standard",
        )}
      >
        {value}
      </span>
      {sublabel && <span className="text-xs text-muted-foreground">{sublabel}</span>}
    </div>
  );
}
