"use client";

import { useEffect, useState } from "react";

interface EtaCountdownProps {
  /** Allocation confirmation time (ISO 8601) — the ETA clock starts here, not "now". */
  createdAt: string;
  /** Travel time to the facility at confirmation, in minutes; null on an estimated-only miss. */
  etaMinutes: number | null;
}

function formatRemaining(ms: number): { label: string; overdue: boolean } {
  const overdue = ms < 0;
  const abs = Math.abs(ms);
  const totalSeconds = Math.floor(abs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const clock = `${minutes}:${seconds.toString().padStart(2, "0")}`;
  return { label: overdue ? `Overdue by ${clock}` : `Arriving in ${clock}`, overdue };
}

/** Ticks every second against a fixed expected-arrival timestamp — no polling, purely local. */
export function EtaCountdown({ createdAt, etaMinutes }: EtaCountdownProps) {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    // First paint happens without a value (see below) to avoid an SSR/client render
    // mismatch — Date.now() would differ between the server render and the client's first
    // tick. Set it once on mount, then tick every second.
    /* eslint-disable-next-line react-hooks/set-state-in-effect */
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  if (etaMinutes === null) {
    return <span className="font-mono text-sm text-muted-foreground">ETA unavailable</span>;
  }
  if (now === null) {
    return <span className="font-mono text-sm text-muted-foreground">…</span>;
  }

  const expectedArrival = new Date(createdAt).getTime() + etaMinutes * 60_000;
  const { label, overdue } = formatRemaining(expectedArrival - now);

  return (
    <span
      className={`font-mono text-sm ${overdue ? "font-medium text-critical" : "text-foreground"}`}
    >
      {label}
    </span>
  );
}
