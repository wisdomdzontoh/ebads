/**
 * Secure key-value store for the auth session — web counterpart of `secureStorage.ts`.
 *
 * `expo-secure-store` is native-only; `localStorage` is the same fallback `storage.web.ts`
 * already uses for settings. A browser has no OS keychain to defer to, so this is the
 * pragmatic ceiling for a web build, not a security downgrade specific to auth.
 */

declare const localStorage: {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
};

const PREFIX = 'ebads.secure.';

export async function getSecureItem(key: string): Promise<string | null> {
  return localStorage.getItem(PREFIX + key);
}

export async function setSecureItem(key: string, value: string): Promise<void> {
  localStorage.setItem(PREFIX + key, value);
}

export async function deleteSecureItem(key: string): Promise<void> {
  localStorage.removeItem(PREFIX + key);
}
