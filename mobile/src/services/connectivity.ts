/**
 * Connectivity detection (docs/05 §3) — the switch between online Dispatch and offline mode.
 *
 * A single source of truth for "is the device online?", built on NetInfo. The strict offline
 * boundary (docs/05 §3) depends on this: when it reports offline, the app must not submit any
 * allocation request. We treat "connected AND internet reachable (or unknown)" as online, so a
 * connected-but-no-internet state correctly falls back to the read-only informational mode.
 */

import NetInfo, { type NetInfoState } from '@react-native-community/netinfo';

/** Reduce a NetInfo state to a single online boolean. */
export function isStateOnline(state: NetInfoState): boolean {
  // `isInternetReachable` can be null (unknown) right after boot — don't block on unknown.
  return Boolean(state.isConnected) && state.isInternetReachable !== false;
}

/** Subscribe to connectivity changes; returns an unsubscribe function. */
export function subscribeConnectivity(listener: (online: boolean) => void): () => void {
  return NetInfo.addEventListener((state) => listener(isStateOnline(state)));
}

/** One-shot connectivity check (used before a manual sync or dispatch attempt). */
export async function checkOnline(): Promise<boolean> {
  return isStateOnline(await NetInfo.fetch());
}
