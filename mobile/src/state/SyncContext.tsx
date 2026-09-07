/**
 * Sync state — the app-wide status of the facility cache (docs/05 §5).
 *
 * Centralises the last-sync bookkeeping and the "Sync now" action so Settings, the offline
 * banner, and the interval/background triggers all share one source of truth. Sync runs
 * whenever online: once when connectivity is (re)gained, then on the configured interval.
 * Failures are surfaced (stale timestamp + error), never hidden (docs/05 §5).
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { registerBackgroundSync } from '../services/backgroundSync';
import { getSyncMeta, type SyncMeta } from '../services/cache';
import { runSync } from '../services/sync';
import { useAuth } from './AuthContext';
import { useConnectivity } from './ConnectivityContext';
import { useSettings } from './SettingsContext';

interface SyncContextValue {
  lastSync: SyncMeta | null;
  syncing: boolean;
  lastError: string | null;
  syncNow: () => Promise<void>;
}

const SyncContext = createContext<SyncContextValue | null>(null);

const MINUTE_MS = 60_000;

export function SyncProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const { settings, ready } = useSettings();
  const { api, session } = useAuth();
  const { online } = useConnectivity();
  const [lastSync, setLastSync] = useState<SyncMeta | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const syncingRef = useRef(false);

  const syncNow = useCallback(async (): Promise<void> => {
    if (syncingRef.current) return; // never overlap sync runs
    syncingRef.current = true;
    setSyncing(true);
    const outcome = await runSync(api);
    setLastError(outcome.ok ? null : outcome.error);
    setLastSync(await getSyncMeta());
    setSyncing(false);
    syncingRef.current = false;
  }, [api]);

  // Load whatever the cache last recorded, so the UI has a timestamp immediately.
  useEffect(() => {
    void getSyncMeta().then(setLastSync);
  }, []);

  // Sync when online AND signed in: `GET /facilities` requires a bearer token now (Increment
  // 1), so a sync attempt before login would only ever produce a 401 the dispatcher can't act
  // on from here — wait for a session instead of surfacing it as a sync failure.
  useEffect(() => {
    if (!ready || !online || !session) return;
    void syncNow();
    const interval = setInterval(() => {
      void syncNow();
    }, Math.max(1, settings.syncIntervalMinutes) * MINUTE_MS);
    return () => clearInterval(interval);
  }, [ready, online, session, settings.syncIntervalMinutes, syncNow]);

  // Register the OS background-refresh task at the configured interval (docs/05 §5). The OS,
  // not this interval, decides when it actually runs; a no-op on web.
  useEffect(() => {
    if (!ready) return;
    void registerBackgroundSync(settings.syncIntervalMinutes);
  }, [ready, settings.syncIntervalMinutes]);

  const value = useMemo<SyncContextValue>(
    () => ({ lastSync, syncing, lastError, syncNow }),
    [lastSync, syncing, lastError, syncNow],
  );

  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

export function useSync(): SyncContextValue {
  const context = useContext(SyncContext);
  if (context === null) {
    throw new Error('useSync must be used within a SyncProvider');
  }
  return context;
}
