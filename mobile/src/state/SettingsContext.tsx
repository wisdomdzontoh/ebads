/**
 * Settings state — engine connection + sync preferences (docs/05 §2.4, docs/09 §11).
 *
 * Holds the base URL, optional API key, background sync interval (default 15 min, docs/09
 * §11), and the push-notifications preference. Values persist across restarts via the KV
 * store, and a memoised `ApiClient` is derived from the current connection settings so every
 * screen talks to the engine the dispatcher configured.
 *
 * Also holds the persisted CONNECTION VERDICT — the outcome of the last explicit "test
 * connection" run (services/connection.ts). Screens read this one shared verdict instead of
 * each discovering a misconfiguration through their own failed requests. Changing the base URL
 * or API key resets the verdict to `untested`, because the old proof no longer applies.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { ApiClient } from '../services/api';
import { getItem, setItem } from '../services/storage';

/** Default background sync interval in minutes (docs/09 §11 `BACKGROUND_SYNC_INTERVAL`). */
export const DEFAULT_SYNC_INTERVAL_MINUTES = 15;
/** Default engine URL; works on web/emulator — set the LAN IP on a physical device. */
export const DEFAULT_BASE_URL = 'http://localhost:8000/api/v1';

export interface Settings {
  baseUrl: string;
  apiKey: string;
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
  /** Facility count returned by the successful test (null otherwise). */
  facilityCount: number | null;
}

const UNTESTED: ConnectionState = {
  status: 'untested',
  message: null,
  checkedAt: null,
  facilityCount: null,
};

interface SettingsContextValue {
  settings: Settings;
  ready: boolean;
  api: ApiClient;
  connection: ConnectionState;
  update: (patch: Partial<Settings>) => Promise<void>;
  setConnection: (state: ConnectionState) => void;
}

const DEFAULTS: Settings = {
  baseUrl: DEFAULT_BASE_URL,
  apiKey: '',
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
          const next = { ...DEFAULTS, ...(JSON.parse(storedSettings) as Partial<Settings>) };
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

  const update = useCallback(
    async (patch: Partial<Settings>): Promise<void> => {
      const current = settingsRef.current;
      const next = { ...current, ...patch };
      settingsRef.current = next;
      setSettings(next);
      // A different engine target invalidates the previous connection proof.
      if (next.baseUrl !== current.baseUrl || next.apiKey !== current.apiKey) {
        setConnection(UNTESTED);
      }
      await setItem(STORAGE_KEY, JSON.stringify(next));
    },
    [setConnection],
  );

  const api = useMemo(
    () => new ApiClient({ baseUrl: settings.baseUrl, apiKey: settings.apiKey || undefined }),
    [settings.baseUrl, settings.apiKey],
  );

  const value = useMemo<SettingsContextValue>(
    () => ({ settings, ready, api, connection, update, setConnection }),
    [settings, ready, api, connection, update, setConnection],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

/** Access settings + the derived engine client. Must be used within `SettingsProvider`. */
export function useSettings(): SettingsContextValue {
  const context = useContext(SettingsContext);
  if (context === null) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}
