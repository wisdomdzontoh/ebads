/**
 * Facility cache (web) — the browser counterpart of `cache.ts`.
 *
 * expo-sqlite on web ships a WebAssembly build that Metro can't bundle without extra config,
 * so on web we back the cache with `localStorage` instead. Metro resolves this `.web` file
 * automatically; native keeps using SQLite. Same public API and same "cache only facility
 * profiles + bed counts" contract (docs/05 §4).
 */

import type { CachedFacility, SyncMeta } from './cache';
import type { Facility } from './types';

// Typed shim so we don't need the DOM lib in tsconfig just for these two calls.
declare const localStorage: {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

const FACILITIES_KEY = 'ebads.facilities';
const META_KEY = 'ebads.syncMeta';

export async function saveFacilities(facilities: Facility[], syncedAt: string): Promise<void> {
  const cached: CachedFacility[] = facilities.map((facility) => ({
    id: facility.id,
    name: facility.name,
    latitude: facility.latitude,
    longitude: facility.longitude,
    tier: facility.tier,
    supported_bed_types: facility.supported_bed_types,
    contact_phone: facility.contact_phone,
    bed_counts: facility.bed_counts,
    synced_at: syncedAt,
  }));
  localStorage.setItem(FACILITIES_KEY, JSON.stringify(cached));
}

export async function loadFacilities(): Promise<CachedFacility[]> {
  const raw = localStorage.getItem(FACILITIES_KEY);
  return raw ? (JSON.parse(raw) as CachedFacility[]) : [];
}

export async function setSyncMeta(meta: SyncMeta): Promise<void> {
  const previousRaw = localStorage.getItem(META_KEY);
  const previous = previousRaw ? (JSON.parse(previousRaw) as SyncMeta) : null;
  // Mirror the native COALESCE: a failed sync keeps the previous timestamp (docs/05 §5).
  const merged: SyncMeta = {
    last_sync_at: meta.last_sync_at ?? previous?.last_sync_at ?? null,
    status: meta.status,
    facility_count: meta.facility_count,
  };
  localStorage.setItem(META_KEY, JSON.stringify(merged));
}

export async function getSyncMeta(): Promise<SyncMeta | null> {
  const raw = localStorage.getItem(META_KEY);
  return raw ? (JSON.parse(raw) as SyncMeta) : null;
}
