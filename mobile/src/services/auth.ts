/**
 * Auth session persistence (EBADS_PRD.md §10) — read/write/clear only, no HTTP.
 *
 * The actual login/refresh calls live on `ApiClient` (services/api.ts), consistent with it
 * being "the app's only channel to the engine". This module just persists what login returns,
 * in the OS keychain/keystore (`secureStorage`), and is deliberately plain async functions
 * rather than a hook — `state/AuthContext.tsx` (React) and `services/backgroundSync.ts` (a bare
 * background task with no React context) both need to read/write the same session.
 */

import { deleteSecureItem, getSecureItem, setSecureItem } from './secureStorage';
import type { Role } from './types';

export interface Session {
  accessToken: string;
  refreshToken: string;
  role: Role;
  facilityId: string | null;
  /** Not returned by `POST /auth/login` — captured from what the dispatcher typed, purely for
   * display (Settings' "Signed in as …"). Never sent back to the engine. */
  email: string;
}

const SESSION_KEY = 'ebads_session';

export async function readSession(): Promise<Session | null> {
  const raw = await getSecureItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null; // corrupt value — treat as signed out rather than crash
  }
}

export async function storeSession(session: Session): Promise<void> {
  await setSecureItem(SESSION_KEY, JSON.stringify(session));
}

/** Persists just the new access token from a refresh, keeping everything else unchanged. */
export async function storeRefreshedAccessToken(
  session: Session,
  accessToken: string,
): Promise<Session> {
  const next = { ...session, accessToken };
  await storeSession(next);
  return next;
}

export async function clearSession(): Promise<void> {
  await deleteSecureItem(SESSION_KEY);
}
