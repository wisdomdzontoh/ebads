/**
 * Notification history (Expo SQLite) — a durable record of every in-app alert the dispatcher
 * has been shown (recommendation, escalation, revocation, arrival), so there is a Notifications
 * screen to browse back through and a "read/unread" state, independent of whatever the OS
 * notification tray itself still shows or has already cleared.
 *
 * A DIFFERENT database file from `services/cache.ts`'s facility cache on purpose — that
 * module's own docstring is explicit that it holds "no request history" (docs/05 §3's
 * client-never-matches boundary is about DATA, this is presentation-layer alert bookkeeping,
 * but keeping them in separate files/tables avoids any future reader conflating the two).
 */

import * as SQLite from 'expo-sqlite';

const DB_NAME = 'ebads-notifications.db';

export type NotificationKind = 'recommendation' | 'escalation' | 'revocation' | 'arrival' | 'other';

/** Where tapping a notification should take the dispatcher. Kept intentionally narrow (this
 * app has four tabs) rather than a free-form deep link. */
export interface NotificationTarget {
  screen: 'Dispatch' | 'History';
}

export interface NotificationRecord {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  createdAt: string;
  read: boolean;
  target: NotificationTarget | null;
}

interface NotificationRow {
  id: string;
  kind: string;
  title: string;
  body: string;
  created_at: string;
  read: number;
  target: string | null;
}

function fromRow(row: NotificationRow): NotificationRecord {
  return {
    id: row.id,
    kind: row.kind as NotificationKind,
    title: row.title,
    body: row.body,
    createdAt: row.created_at,
    read: row.read === 1,
    target: row.target ? (JSON.parse(row.target) as NotificationTarget) : null,
  };
}

let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

async function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (dbPromise === null) {
    dbPromise = SQLite.openDatabaseAsync(DB_NAME).then(async (db) => {
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS notifications (
          id TEXT PRIMARY KEY NOT NULL,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          created_at TEXT NOT NULL,
          read INTEGER NOT NULL DEFAULT 0,
          target TEXT
        );
      `);
      return db;
    });
  }
  return dbPromise;
}

/** How many past notifications to keep — a rolling window, not unbounded growth. */
const MAX_RECORDS = 200;

export async function recordNotification(input: {
  kind: NotificationKind;
  title: string;
  body: string;
  target?: NotificationTarget;
}): Promise<NotificationRecord> {
  const db = await getDb();
  const record: NotificationRecord = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    kind: input.kind,
    title: input.title,
    body: input.body,
    createdAt: new Date().toISOString(),
    read: false,
    target: input.target ?? null,
  };
  await db.runAsync(
    'INSERT INTO notifications (id, kind, title, body, created_at, read, target) VALUES (?, ?, ?, ?, ?, ?, ?)',
    record.id,
    record.kind,
    record.title,
    record.body,
    record.createdAt,
    0,
    record.target ? JSON.stringify(record.target) : null,
  );
  // Trim beyond the rolling window in the same call — this is the only write path.
  await db.runAsync(
    'DELETE FROM notifications WHERE id NOT IN (SELECT id FROM notifications ORDER BY created_at DESC LIMIT ?)',
    MAX_RECORDS,
  );
  return record;
}

export async function listNotifications(): Promise<NotificationRecord[]> {
  const db = await getDb();
  const rows = await db.getAllAsync<NotificationRow>(
    'SELECT * FROM notifications ORDER BY created_at DESC',
  );
  return rows.map(fromRow);
}

export async function markNotificationRead(id: string): Promise<void> {
  const db = await getDb();
  await db.runAsync('UPDATE notifications SET read = 1 WHERE id = ?', id);
}

export async function markAllNotificationsRead(): Promise<void> {
  const db = await getDb();
  await db.runAsync('UPDATE notifications SET read = 1 WHERE read = 0');
}

export async function unreadNotificationCount(): Promise<number> {
  const db = await getDb();
  const row = await db.getFirstAsync<{ count: number }>(
    'SELECT COUNT(*) as count FROM notifications WHERE read = 0',
  );
  return row?.count ?? 0;
}
