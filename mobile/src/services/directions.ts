/**
 * Google Directions — the real road route for in-app, live navigation (not the external Maps
 * app hand-off this replaces). Used only for PRESENTATION: drawing the route line and seeding
 * the live ETA/distance the navigation view then counts down locally (services/maps.ts's own
 * docstring principle applies here too — building a URL/decoding a path is not "matching").
 *
 * Degrades the same way the rest of the app does: no key, a network failure, or a non-OK
 * Directions status all fall back to `route: null` — the caller draws a straight line between
 * the two points and estimates from Haversine distance instead of crashing or silently doing
 * nothing. Unlike an earlier version of this module, the REASON for a failure is also returned
 * (not just swallowed to `null`) — a Google API key that is restricted to "Android apps"/"iOS
 * apps" (the restriction `README.md` tells you to set for the native Maps SDK to work) makes
 * every call from here fail with `REQUEST_DENIED`, because a plain `fetch()` from JS does not
 * carry the app-signature headers that restriction checks for — that failure looked identical
 * to "no network" until the reason was surfaced, so it was silently indistinguishable from
 * "GPS not ready" in the UI. If live routing is failing in practice, check that message first.
 */

import { GOOGLE_MAPS_API_KEY } from './maps';

// A key restricted to "Android apps"/"iOS apps" (what the Maps SDK needs, README.md) rejects
// this module's plain fetch() calls with REQUEST_DENIED — they carry no app-signature headers
// for that restriction to check. EXPO_PUBLIC_GOOGLE_DIRECTIONS_API_KEY lets a second,
// unrestricted (or API-restricted-only) key be used for Directions specifically; falls back to
// the Maps SDK key so nothing breaks for a setup that hasn't split the keys yet (e.g. because
// the single key's Application restrictions were relaxed to None instead).
const DIRECTIONS_API_KEY: string =
  process.env.EXPO_PUBLIC_GOOGLE_DIRECTIONS_API_KEY ?? GOOGLE_MAPS_API_KEY;

export interface LatLng {
  latitude: number;
  longitude: number;
}

export interface RouteResult {
  /** Road path from origin to destination, in drawing order. */
  path: LatLng[];
  distanceMeters: number;
  durationSeconds: number;
}

export interface RouteOutcome {
  route: RouteResult | null;
  /** Human-readable reason `route` is null — the actual Google API status/error_message when
   * available, so a misconfigured key (see module docstring) is visible instead of guessed at. */
  error: string | null;
}

const REQUEST_TIMEOUT_MS = 8000;

/** Decode a Google encoded polyline (the standard algorithm — see Google's Directions/Roads
 * API docs) into a list of coordinates. No external dependency for ~30 lines of well-known,
 * stable math. */
function decodePolyline(encoded: string): LatLng[] {
  const points: LatLng[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    let result = 0;
    let shift = 0;
    let byte: number;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;

    result = 0;
    shift = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;

    points.push({ latitude: lat / 1e5, longitude: lng / 1e5 });
  }
  return points;
}

/** Fetch the driving route between two points. `route` is `null` on any failure — check `error`
 * for why (see module docstring: a restricted API key is the most common real-world cause). */
export async function getRoute(origin: LatLng, destination: LatLng): Promise<RouteOutcome> {
  if (!DIRECTIONS_API_KEY) {
    return { route: null, error: 'No Google Maps API key configured (EXPO_PUBLIC_GOOGLE_MAPS_API_KEY).' };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const params = new URLSearchParams({
      origin: `${origin.latitude},${origin.longitude}`,
      destination: `${destination.latitude},${destination.longitude}`,
      mode: 'driving',
      key: DIRECTIONS_API_KEY,
    });
    const response = await fetch(
      `https://maps.googleapis.com/maps/api/directions/json?${params.toString()}`,
      { signal: controller.signal },
    );
    if (!response.ok) {
      return { route: null, error: `Directions request failed (HTTP ${response.status}).` };
    }
    const body = (await response.json()) as {
      status: string;
      error_message?: string;
      routes?: {
        overview_polyline?: { points: string };
        legs?: { distance?: { value: number }; duration?: { value: number } }[];
      }[];
    };
    if (body.status !== 'OK' || !body.routes?.length) {
      // Surface Google's own status/error_message verbatim — e.g. REQUEST_DENIED means the API
      // key's restrictions are rejecting this call (see module docstring), ZERO_RESULTS means no
      // driving route exists, OVER_QUERY_LIMIT means billing/quota — each needs a different fix.
      const detail = body.error_message ? `: ${body.error_message}` : '';
      return { route: null, error: `Directions API returned ${body.status}${detail}` };
    }

    const route = body.routes[0];
    const leg = route.legs?.[0];
    const encoded = route.overview_polyline?.points;
    if (!leg?.distance || !leg.duration || !encoded) {
      return { route: null, error: 'Directions API returned an incomplete route.' };
    }

    return {
      route: {
        path: decodePolyline(encoded),
        distanceMeters: leg.distance.value,
        durationSeconds: leg.duration.value,
      },
      error: null,
    };
  } catch (err) {
    const message = err instanceof Error && err.name === 'AbortError' ? 'timed out' : 'network error';
    return { route: null, error: `Directions request failed (${message}).` };
  } finally {
    clearTimeout(timer);
  }
}
