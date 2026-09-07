/**
 * Google Directions — the real road route for in-app, live navigation (not the external Maps
 * app hand-off this replaces). Used only for PRESENTATION: drawing the route line and seeding
 * the live ETA/distance the navigation view then counts down locally (services/maps.ts's own
 * docstring principle applies here too — building a URL/decoding a path is not "matching").
 *
 * Degrades the same way the rest of the app does: no key, a network failure, or a non-OK
 * Directions status all fall back to `null` — the caller draws a straight line between the two
 * points and estimates from Haversine distance instead of crashing or silently doing nothing.
 */

import { GOOGLE_MAPS_API_KEY } from './maps';

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

/** Fetch the driving route between two points, or `null` if unavailable (see module docstring). */
export async function getRoute(origin: LatLng, destination: LatLng): Promise<RouteResult | null> {
  if (!GOOGLE_MAPS_API_KEY) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const params = new URLSearchParams({
      origin: `${origin.latitude},${origin.longitude}`,
      destination: `${destination.latitude},${destination.longitude}`,
      mode: 'driving',
      key: GOOGLE_MAPS_API_KEY,
    });
    const response = await fetch(
      `https://maps.googleapis.com/maps/api/directions/json?${params.toString()}`,
      { signal: controller.signal },
    );
    if (!response.ok) return null;
    const body = (await response.json()) as {
      status: string;
      routes?: {
        overview_polyline?: { points: string };
        legs?: { distance?: { value: number }; duration?: { value: number } }[];
      }[];
    };
    if (body.status !== 'OK' || !body.routes?.length) return null;

    const route = body.routes[0];
    const leg = route.legs?.[0];
    const encoded = route.overview_polyline?.points;
    if (!leg?.distance || !leg.duration || !encoded) return null;

    return {
      path: decodePolyline(encoded),
      distanceMeters: leg.distance.value,
      durationSeconds: leg.duration.value,
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
