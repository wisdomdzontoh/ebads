/**
 * Live GPS position — shared by `LiveNavigationMap` (native + web) so in-app navigation gets a
 * position fast and reliably, instead of waiting on `watchPositionAsync`'s first callback
 * alone, which can take a while (or never arrive) on a cold GPS fix and silently leaves the
 * screen showing "Waiting for GPS…" forever with no route, no distance, no ETA — the exact
 * failure this hook exists to prevent.
 *
 * Acquisition order, each one only filling a gap the previous step left:
 *  1. `fallback` (e.g. the incident's own coordinates, already known from the dispatch form) —
 *     set immediately, synchronously, so the map/route render something on the very first
 *     paint instead of a blank "waiting" state.
 *  2. `getLastKnownPositionAsync` — the device's cached last fix, near-instant when present.
 *  3. `getCurrentPositionAsync` (Balanced accuracy, for speed) — a real fresh fix, raced
 *     against a timeout so a weak signal can't hang the screen indefinitely.
 *  4. `watchPositionAsync` (High accuracy) — continuous live tracking from here on; every
 *     update clears `usingFallback` and `error`, since it proves GPS is actually working now.
 */

import * as Location from 'expo-location';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface LatLng {
  latitude: number;
  longitude: number;
}

export interface LiveLocationState {
  position: LatLng | null;
  /** True while `position` is the caller's `fallback`, not a real device fix — callers should
   * label the map/readout accordingly rather than presenting it as a live GPS position. */
  usingFallback: boolean;
  /** Human-readable, only set on permission/acquisition failure — never on a plain "still
   * looking" state, which the caller should render as "Waiting for GPS…", not an error. */
  error: string | null;
  /** Re-runs the whole acquisition sequence — offered to the dispatcher after a failure. */
  retry: () => void;
}

const FIRST_FIX_TIMEOUT_MS = 8000;
// Discard a watch update whose reported accuracy is worse than this (metres) — a coarse,
// cell-tower-grade fix jumping into the position feed is exactly what previously caused a
// live-navigation route to recompute from a wrong origin and show a worse route/ETA than the
// real one. `accuracy` is sometimes null on some platforms/devices — those updates are kept
// (no accuracy figure to reject on), not discarded.
const MAX_ACCEPTABLE_ACCURACY_M = 100;

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | null> {
  return Promise.race([
    promise,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), ms)),
  ]);
}

export function useLiveLocation(fallback: LatLng | null): LiveLocationState {
  const [position, setPosition] = useState<LatLng | null>(fallback);
  const [usingFallback, setUsingFallback] = useState(fallback !== null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let active = true;
    let subscription: Location.LocationSubscription | null = null;

    void (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (!active) return;
      if (status !== 'granted') {
        setError('Location access is off — enable it in system settings for live navigation.');
        if (fallbackRef.current) {
          setPosition(fallbackRef.current);
          setUsingFallback(true);
        }
        return;
      }
      setError(null);

      // Step 2: near-instant cached fix, if the OS has one.
      try {
        const lastKnown = await Location.getLastKnownPositionAsync();
        if (active && lastKnown) {
          setPosition({ latitude: lastKnown.coords.latitude, longitude: lastKnown.coords.longitude });
          setUsingFallback(false);
        }
      } catch {
        // No cached fix — steps 3/4 still run.
      }

      // Step 3: a real fresh fix, capped so a weak signal can't hang the screen.
      try {
        const fresh = await withTimeout(
          Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
          FIRST_FIX_TIMEOUT_MS,
        );
        if (active && fresh) {
          setPosition({ latitude: fresh.coords.latitude, longitude: fresh.coords.longitude });
          setUsingFallback(false);
        }
      } catch {
        // Fall through to the live watch below — it may still succeed.
      }

      // Step 4: continuous live tracking.
      try {
        subscription = await Location.watchPositionAsync(
          { accuracy: Location.Accuracy.High, timeInterval: 3000, distanceInterval: 15 },
          (update) => {
            if (!active) return;
            const accuracy = update.coords.accuracy;
            if (accuracy != null && accuracy > MAX_ACCEPTABLE_ACCURACY_M) return; // too coarse
            setPosition({ latitude: update.coords.latitude, longitude: update.coords.longitude });
            setUsingFallback(false);
            setError(null);
          },
        );
      } catch {
        if (active && position === null) {
          setError('Could not read the device location. Live navigation needs GPS.');
        }
      }
    })();

    return () => {
      active = false;
      subscription?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `fallback` is read via ref (see
    // fallbackRef) so a change to it never restarts an already-running GPS watch; `attempt` is
    // the only thing that should re-run this effect (an explicit `retry()`).
  }, [attempt]);

  return { position, usingFallback, error, retry };
}
