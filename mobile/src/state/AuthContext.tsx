/**
 * Auth state (EBADS_PRD.md §10) — the signed-in dispatcher, the bearer-token session, and the
 * one `ApiClient` instance every screen calls the engine through.
 *
 * Owns the `ApiClient`, pointed at the fixed `ENGINE_BASE_URL` (services/env.ts) plus this
 * provider's own token half. A 401 from any request triggers exactly one refresh attempt
 * (single-flight: concurrent 401s share it); a failed refresh clears the session, which
 * `App.tsx` reads to fall back to `LoginScreen`.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { ApiClient } from '../services/api';
import { clearSession, readSession, storeSession, type Session } from '../services/auth';
import { ENGINE_BASE_URL } from '../services/env';

interface AuthContextValue {
  session: Session | null;
  ready: boolean;
  api: ApiClient;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  // The client's callbacks close over this ref, not `session` state directly, so a request
  // in flight always reads the LATEST token even if a re-render hasn't happened yet.
  const sessionRef = useRef<Session | null>(null);
  const refreshInFlight = useRef<Promise<string | null> | null>(null);

  useEffect(() => {
    let active = true;
    void readSession().then((stored) => {
      if (!active) return;
      sessionRef.current = stored;
      setSession(stored);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const setAndPersist = useCallback((next: Session | null): void => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    setAndPersist(null);
    await clearSession();
  }, [setAndPersist]);

  // Single-flight refresh: concurrent 401s from several in-flight requests share one call to
  // POST /auth/refresh instead of each racing their own.
  const refreshOnce = useCallback(
    (client: ApiClient): Promise<string | null> => {
      if (!refreshInFlight.current) {
        refreshInFlight.current = (async () => {
          const current = sessionRef.current;
          if (!current) return null;
          try {
            const { access_token } = await client.refreshAccessToken(current.refreshToken);
            const next = { ...current, accessToken: access_token };
            await storeSession(next);
            setAndPersist(next);
            return access_token;
          } catch {
            // Refresh token itself is invalid/expired — force sign-out (App.tsx falls back
            // to LoginScreen); never leave the app silently retrying a dead session forever.
            await logout();
            return null;
          }
        })().finally(() => {
          refreshInFlight.current = null;
        });
      }
      return refreshInFlight.current;
    },
    [logout, setAndPersist],
  );

  // Built once (ENGINE_BASE_URL is a build-time constant, services/env.ts, not a setting that
  // changes at runtime) — the callbacks below always read the CURRENT token/refresh via the
  // ref/closure, so the client itself never goes stale across logins/logouts.
  const api = useMemo(() => {
    const client: ApiClient = new ApiClient({
      baseUrl: ENGINE_BASE_URL,
      getAccessToken: () => sessionRef.current?.accessToken ?? null,
      onUnauthorized: () => refreshOnce(client),
    });
    return client;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `client` self-reference is intentional (see above)
  }, [refreshOnce]);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const tokens = await api.login({ email, password });
      const next: Session = {
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        role: tokens.role,
        facilityId: tokens.facility_id,
        email,
      };
      await storeSession(next);
      setAndPersist(next);
    },
    [api, setAndPersist],
  );

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<void> => {
      await api.changePassword({ current_password: currentPassword, new_password: newPassword });
    },
    [api],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ session, ready, api, login, logout, changePassword }),
    [session, ready, api, login, logout, changePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
