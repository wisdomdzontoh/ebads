/**
 * Settings state — sync + notification preferences (docs/09 §11).
 *
 * Holds the background sync interval (default 15 min, docs/09 §11) and the push-notifications
 * preference. Values persist across restarts via the KV store. The engine's location
 * (`services/env.ts::ENGINE_BASE_URL`) and auth (`state/AuthContext.tsx`) are both separate
 * concerns now — this context used to also own an editable base URL, but that was a build-time
 * constant wearing a dispatcher-facing text field: nobody should ever need to type it, and a
 * mistyped one was a support burden with no upside. See `services/env.ts`'s own docstring.
 *
 * Also holds the persisted CONNECTION VERDICT — the outcome of the last explicit "test
 * connection" run (services/connection.ts), a plain reachability probe (`/healthz`, no auth) —
 * screens read this one shared verdict instead of each discovering a misconfiguration through
 * their own failed requests.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { getItem, setItem } from '../services/storage';

/** Default background sync interval in minutes (docs/09 §11 `BACKGROUND_SYNC_INTERVAL`). */
export const DEFAULT_SYNC_INTERVAL_MINUTES = 15;

export interface Settings {
  syncIntervalMinutes: number;
  pushEnabled: boolean;
  /** True once the dispatcher has completed the one-time onboarding flow (docs/05). */
  onboarded: boolean;
}

/** The persisted outcome of the last explicit connection test. */
export interface ConnectionState {
  status: 'untested' | 'ok' | 'failed';
  /** Human-readable failure reason (null when untested/ok). */
  message: string | null;
  /** ISO timestamp of the last test run (null when untested). */
  checkedAt: string | null;
}

const UNTESTED: ConnectionState = { status: 'untested', message: null, checkedAt: null };

interface SettingsContextValue {
  settings: Settings;
  ready: boolean;
  connection: ConnectionState;
  update: (patch: Partial<Settings>) => Promise<void>;
  setConnection: (state: ConnectionState) => void;
}

const DEFAULTS: Settings = {
  syncIntervalMinutes: DEFAULT_SYNC_INTERVAL_MINUTES,
  pushEnabled: true,
  onboarded: false,
};

const STORAGE_KEY = 'settings';
const CONNECTION_KEY = 'connection_state';

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [connection, setConnectionState] = useState<ConnectionState>(UNTESTED);
  const [ready, setReady] = useState(false);
  // Latest committed settings, so `update` can diff without a stale closure.
  const settingsRef = useRef<Settings>(DEFAULTS);

  // Load persisted settings + connection verdict once on mount, merging over the defaults.
  useEffect(() => {
    let active = true;
    void (async () => {
      const [storedSettings, storedConnection] = await Promise.all([
        getItem(STORAGE_KEY),
        getItem(CONNECTION_KEY),
      ]);
      if (active && storedSettings) {
        try {
          const parsed = JSON.parse(storedSettings) as Partial<Settings> & {
            apiKey?: string;
            baseUrl?: string;
          };
          // `apiKey` (pre-JWT scheme, Increment 1) and `baseUrl` (now a build-time constant,
          // services/env.ts) are both retired fields — dropped here rather than left in
          // storage, so a stale persisted value can never leak anywhere or shadow the env var.
          delete parsed.apiKey;
          delete parsed.baseUrl;
          const next = { ...DEFAULTS, ...parsed };
          settingsRef.current = next;
          setSettings(next);
        } catch {
          // Corrupt value — fall back to defaults rather than crashing.
        }
      }
      if (active && storedConnection) {
        try {
          setConnectionState({ ...UNTESTED, ...(JSON.parse(storedConnection) as Partial<ConnectionState>) });
        } catch {
          // Corrupt value — treat as untested.
        }
      }
      if (active) setReady(true);
    })();
    return () => {
      active = false;
    };
  }, []);

  const setConnection = useCallback((state: ConnectionState): void => {
    setConnectionState(state);
    void setItem(CONNECTION_KEY, JSON.stringify(state));
  }, []);

  const update = useCallback(async (patch: Partial<Settings>): Promise<void> => {
    const next = { ...settingsRef.current, ...patch };
    settingsRef.current = next;
    setSettings(next);
    await setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const value = useMemo<SettingsContextValue>(
    () => ({ settings, ready, connection, update, setConnection }),
    [settings, ready, connection, update, setConnection],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

/** Access sync/notification settings. Must be used within `SettingsProvider`. For the engine
 * URL, import `ENGINE_BASE_URL` from `services/env.ts`; for the API client, use `useAuth()`
 * (state/AuthContext.tsx) — it owns the bearer token. */
export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (context === null) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}
