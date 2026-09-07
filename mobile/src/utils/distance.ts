/** Small formatting helpers for the live-navigation distance/ETA readout. */

/** `850 m` under 1 km, else `2.4 km`. */
export function formatDistanceMeters(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

/** `12:05` (mm:ss) — negative input (overdue) still renders as a positive clock; the caller
 * decides how to label an overdue state, this only formats the magnitude. */
export function formatDurationClock(seconds: number): string {
  const total = Math.max(0, Math.round(Math.abs(seconds)));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/** Great-circle distance in metres — used only to scale a fixed route's remaining distance as
 * the vehicle moves, never to pick or rank a facility (docs/05 §8: presentation only). */
export function haversineMeters(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number },
): number {
  const R = 6_371_008.8; // mean Earth radius, metres
  const toRad = (deg: number): number => (deg * Math.PI) / 180;
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.latitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
