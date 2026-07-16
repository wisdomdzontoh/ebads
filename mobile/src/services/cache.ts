/**
 * Local facility cache (Expo SQLite) — the read-only data that powers the Map screen and the
 * offline informational mode (docs/05 §4).
 *
 * The cache stores ONLY facility profiles + last-known bed counts (docs/05 §3): there is
 * deliberately no request history and no matching state, because the client never matches.
 * `synced_at` travels with the data so the UI can always show how fresh it is (and flag it as
 * stale rather than pretending success — docs/05 §5). Serialization is split into pure helpers
 * so it can be unit-tested without a native database.
 */

import * as SQLite from 'expo-sqlite';

import type { BedCount, BedType, Facility, Tier } from './types';

const DB_NAME = 'ebads-cache.db';

/** A facility as held in the cache: the display fields plus when it was last synced. */
export interface CachedFacility {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  tier: Tier;
  supported_bed_types: BedType[];
  contact_phone: string;
  bed_counts: BedCount[];
  synced_at: string;
}

/** Last-sync bookkeeping surfaced in Settings (docs/05 §5). */
export interface SyncMeta {
  last_sync_at: string | null;
  status: 'success' | 'failed';
  facility_count: number;
}

/** The raw column shape of a `facilities` row (JSON columns still stringified). */
interface FacilityRow {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  tier: string;
  supported_bed_types: string;
  contact_phone: string;
  bed_counts: string;
  synced_at: string;
}

/** Flatten an API facility into cache-row values (pure — unit-testable without SQLite). */
export function toRow(facility: Facility, syncedAt: string): FacilityRow {
  return {
    id: facility.id,
    name: facility.name,
    latitude: facility.latitude,
    longitude: facility.longitude,
    tier: facility.tier,
    supported_bed_types: JSON.stringify(facility.supported_bed_types),
    contact_phone: facility.contact_phone,
    bed_counts: JSON.stringify(facility.bed_counts),
    synced_at: syncedAt,
  };
}

/** Rebuild a display facility from a cache row (pure — inverse of `toRow`). */
export function fromRow(row: FacilityRow): CachedFacility {
  return {
    id: row.id,
    name: row.name,
    latitude: row.latitude,
    longitude: row.longitude,
    tier: row.tier as Tier,
    supported_bed_types: JSON.parse(row.supported_bed_types) as BedType[],
    contact_phone: row.contact_phone,
    bed_counts: JSON.parse(row.bed_counts) as BedCount[],
    synced_at: row.synced_at,
  };
}

let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

/** Open (once) and migrate the cache database. */
async function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (dbPromise === null) {
    dbPromise = SQLite.openDatabaseAsync(DB_NAME).then(async (db) => {
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS facilities (
          id TEXT PRIMARY KEY NOT NULL,
          name TEXT NOT NULL,
          latitude REAL NOT NULL,
          longitude REAL NOT NULL,
          tier TEXT NOT NULL,
          supported_bed_types TEXT NOT NULL,
          contact_phone TEXT NOT NULL,
          bed_counts TEXT NOT NULL,
          synced_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_meta (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          last_sync_at TEXT,
          status TEXT NOT NULL,
          facility_count INTEGER NOT NULL
        );
      `);
      return db;
    });
  }
  return dbPromise;
}

/** Replace the cached facility set with a freshly fetched one, stamping `syncedAt`. */
export async function saveFacilities(facilities: Facility[], syncedAt: string): Promise<void> {
  const db = await getDb();
  await db.withTransactionAsync(async () => {
    await db.execAsync('DELETE FROM facilities;');
    for (const facility of facilities) {
      const row = toRow(facility, syncedAt);
      await db.runAsync(
        `INSERT INTO facilities
           (id, name, latitude, longitude, tier, supported_bed_types, contact_phone, bed_counts, synced_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        row.id,
        row.name,
        row.latitude,
        row.longitude,
        row.tier,
        row.supported_bed_types,
        row.contact_phone,
        row.bed_counts,
        row.synced_at,
      );
    }
  });
}

/** Return every cached facility, ordered by name (the offline / map data source). */
export async function loadFacilities(): Promise<CachedFacility[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<FacilityRow>('SELECT * FROM facilities ORDER BY name;');
  return rows.map(fromRow);
}

/** Record the outcome of a sync attempt (success updates the timestamp; failure keeps it). */
export async function setSyncMeta(meta: SyncMeta): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    `INSERT INTO sync_meta (id, last_sync_at, status, facility_count)
       VALUES (1, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         last_sync_at = COALESCE(excluded.last_sync_at, sync_meta.last_sync_at),
         status = excluded.status,
         facility_count = excluded.facility_count`,
    meta.last_sync_at,
    meta.status,
    meta.facility_count,
  );
}

/** Read the last-sync bookkeeping, or null if the cache has never synced. */
export async function getSyncMeta(): Promise<SyncMeta | null> {
  const db = await getDb();
  const row = await db.getFirstAsync<SyncMeta>('SELECT last_sync_at, status, facility_count FROM sync_meta WHERE id = 1;');
  return row ?? null;
}
