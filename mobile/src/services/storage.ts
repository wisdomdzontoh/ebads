/**
 * Tiny key-value store (Expo SQLite) for app settings persistence.
 *
 * Settings (engine base URL, API key, sync interval, push preference) must survive restarts.
 * Rather than add another dependency we reuse SQLite with a small `kv` table. Values are
 * plain strings; callers serialise as needed. Kept separate from the facility cache DB so the
 * two concerns are independent.
 */

import * as SQLite from 'expo-sqlite';

const DB_NAME = 'ebads-settings.db';

let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

async function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (dbPromise === null) {
    dbPromise = SQLite.openDatabaseAsync(DB_NAME).then(async (db) => {
      await db.execAsync(
        'CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL);',
      );
      return db;
    });
  }
  return dbPromise;
}

export async function getItem(key: string): Promise<string | null> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ value: string }>('SELECT value FROM kv WHERE key = ?;', key);
  return row?.value ?? null;
}

export async function setItem(key: string, value: string): Promise<void> {
  const db = await getDb();
  await db.runAsync(
    'INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value;',
    key,
    value,
  );
}
