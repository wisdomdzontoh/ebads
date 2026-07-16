/**
 * Facility cache synchronisation (docs/05 §5).
 *
 * Pulls `GET /facilities` and writes the result into the local cache, stamping the sync time.
 * Sync is **best-effort**: on failure it records a `failed` status while KEEPING the previous
 * `last_sync_at`, so the UI shows stale data honestly and never a silent success (docs/05 §5).
 * The same function is driven by three triggers — app foreground interval, the Settings "Sync
 * now" button, and the registered background task — so there is one sync code path.
 */

import type { ApiClient } from './api';
import { getSyncMeta, saveFacilities, setSyncMeta, type SyncMeta } from './cache';

export type SyncOutcome =
  | { ok: true; syncedAt: string; count: number }
  | { ok: false; error: string; lastSyncAt: string | null };

/** Run one sync: fetch facilities, replace the cache, and record the outcome. */
export async function runSync(api: ApiClient): Promise<SyncOutcome> {
  try {
    const facilities = await api.getFacilities();
    const syncedAt = new Date().toISOString();
    await saveFacilities(facilities, syncedAt);
    await setSyncMeta({
      last_sync_at: syncedAt,
      status: 'success',
      facility_count: facilities.length,
    });
    return { ok: true, syncedAt, count: facilities.length };
  } catch (error) {
    // Keep the previous timestamp; only flip the status to `failed` (never a silent success).
    const previous = await getSyncMeta();
    const meta: SyncMeta = {
      last_sync_at: previous?.last_sync_at ?? null,
      status: 'failed',
      facility_count: previous?.facility_count ?? 0,
    };
    await setSyncMeta(meta);
    const message = error instanceof Error ? error.message : 'sync failed';
    return { ok: false, error: message, lastSyncAt: meta.last_sync_at };
  }
}
