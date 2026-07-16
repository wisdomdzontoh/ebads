/**
 * Dynamic Expo config — overlays the static app.json with the Google Maps API key read from
 * the environment (EXPO_PUBLIC_GOOGLE_MAPS_API_KEY), so the key is never committed. The same
 * key drives Google Maps on Android (`android.config.googleMaps.apiKey`), iOS
 * (`ios.config.googleMapsApiKey`), and the web static-map images.
 */

const googleMapsApiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY ?? '';

module.exports = ({ config }) => ({
  ...config,
  ios: {
    ...config.ios,
    config: { ...(config.ios?.config ?? {}), googleMapsApiKey },
  },
  android: {
    ...config.android,
    config: { ...(config.android?.config ?? {}), googleMaps: { apiKey: googleMapsApiKey } },
  },
});
