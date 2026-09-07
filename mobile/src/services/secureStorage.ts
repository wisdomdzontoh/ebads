/**
 * Secure key-value store for the auth session (access/refresh tokens) — native.
 *
 * Separate from `storage.ts` (plain SQLite) deliberately: refresh tokens are long-lived
 * bearer credentials, not app preferences, so they belong in the OS keychain/keystore
 * (`expo-secure-store`), not a plaintext SQLite file. Read both by `state/AuthContext.tsx`
 * (React) and `services/backgroundSync.ts` (a bare background task, no React context) — kept
 * as plain async functions for exactly that reason.
 */

import * as SecureStore from 'expo-secure-store';

export async function getSecureItem(key: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    // Keychain/keystore can be unavailable (e.g. a locked device) — treat as "nothing stored"
    // rather than crash; the caller falls back to its logged-out state.
    return null;
  }
}

export async function setSecureItem(key: string, value: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(key, value);
  } catch {
    // Best-effort: a failed write means the session won't survive a restart, not a crash now.
  }
}

export async function deleteSecureItem(key: string): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    // Nothing to clean up, or the store is unavailable — either way, not fatal.
  }
}
