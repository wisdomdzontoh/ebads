/**
 * Google Maps configuration + Static Maps helper.
 *
 * On native, react-native-maps renders Google Maps directly (PROVIDER_GOOGLE). On web (where
 * react-native-maps is unavailable) we render a Google Static Maps image, so every map surface
 * is Google Maps. The API key comes from `EXPO_PUBLIC_GOOGLE_MAPS_API_KEY` (inlined by Expo at
 * build time) — never hardcoded. Building a URL is not "matching"; it is pure presentation.
 */

export const GOOGLE_MAPS_API_KEY: string = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY ?? '';

export interface LatLng {
  latitude: number;
  longitude: number;
}

export interface StaticMarker extends LatLng {
  color?: string;
}

/** Build a Google Static Maps image URL for a centred view with optional markers and an
 * optional drawn path (the live-navigation web fallback's route line, `LiveNavigationMap.web`
 * — `react-native-maps`' `Polyline` is native-only, this is the closest web equivalent). */
export function staticMapUrl(options: {
  center: LatLng;
  zoom?: number;
  width?: number;
  height?: number;
  markers?: StaticMarker[];
  /** Drawn as a solid line through every point, in order — e.g. a decoded route path. */
  path?: LatLng[];
}): string {
  const { center, zoom = 12, width = 640, height = 360, markers = [], path = [] } = options;
  const base = 'https://maps.googleapis.com/maps/api/staticmap';
  const params = [
    `center=${center.latitude},${center.longitude}`,
    `zoom=${zoom}`,
    `size=${width}x${height}`,
    'scale=2',
    ...markers.map(
      (marker) => `markers=color:${marker.color ?? 'red'}%7C${marker.latitude},${marker.longitude}`,
    ),
    ...(path.length > 1
      ? [
          // weight:7 — thick, high-contrast route line (Bolt/Uber-style); 4 read as thin
          // against a busy street map.
          `path=color:0x0A616BCC%7Cweight:7%7C${path
            .map((point) => `${point.latitude},${point.longitude}`)
            .join('%7C')}`,
        ]
      : []),
    `key=${GOOGLE_MAPS_API_KEY}`,
  ];
  return `${base}?${params.join('&')}`;
}
