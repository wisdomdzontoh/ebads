/** Small time-formatting helpers for sync freshness labels (docs/05 §3, §5). */

function pad(value: number): string {
  return value.toString().padStart(2, '0');
}

/** Local wall-clock `HH:MM` for an ISO timestamp. */
export function formatClock(iso: string): string {
  const date = new Date(iso);
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Whole minutes elapsed since an ISO timestamp (never negative). */
export function minutesAgo(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60_000));
}

/** Human sync label, e.g. `14 min ago (09:27)` — or `never synced` when there is no data. */
export function lastSyncLabel(iso: string | null): string {
  if (!iso) return 'never synced';
  const minutes = minutesAgo(iso);
  const relative = minutes < 1 ? 'just now' : `${minutes} min ago`;
  return `${relative} (${formatClock(iso)})`;
}
