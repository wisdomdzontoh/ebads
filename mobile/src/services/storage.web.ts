/**
 * Key-value settings store (web) — `localStorage` counterpart of `storage.ts`.
 *
 * Keeps expo-sqlite out of the web bundle (see `cache.web.ts`). Same API as the native store.
 */

declare const localStorage: {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

const PREFIX = 'ebads.kv.';

export async function getItem(key: string): Promise<string | null> {
  return localStorage.getItem(PREFIX + key);
}

export async function setItem(key: string, value: string): Promise<void> {
  localStorage.setItem(PREFIX + key, value);
}
