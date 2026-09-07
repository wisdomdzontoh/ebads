# EBADS Dispatcher (mobile)

React Native + Expo thin client for NAS dispatchers (docs/05). The app **renders engine
decisions only** — it never scores, filters, or ranks (a guard test enforces this).

> **Toolchain note:** docs/05 pins Expo SDK 51, but this project targets **Expo SDK 56**
> (the latest stable SDK the store Expo Go supports — SDK 57 is too new for Expo Go, and
> SDK 51 predates the local Node v25 runtime). All dependencies are pinned to the SDK-56
> set, so a plain `npm install` resolves with **no `--legacy-peer-deps`**. The architecture
> (thin client, offline boundary, cache/sync) is unchanged. `[IMPL]`

## Run

```bash
cd mobile
npm start            # then press w (web), a (Android), or i (iOS)
npm test             # Jest: services + the no-client-matching guard
npm run typecheck    # tsc --noEmit (strict)
```

## Google Maps

All map UI uses Google Maps: react-native-maps with `PROVIDER_GOOGLE` on native, and Google
Static Maps images on web. Provide a key:

```bash
cp .env.example .env      # then set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY=<your key>
```

Enable **Maps SDK for Android/iOS** and **Maps Static API** for the key. `app.config.js`
injects it into the native builds automatically.

**If a map renders blank / invisible:**

- **Native (dev build/APK):** the key is baked in at **build** time. If `.env` (or the EAS env
  var) was missing or wrong when the build was made, Google Maps renders an empty beige canvas
  — the app now shows a "Google Maps key missing" chip in that case. Fix the env var and
  **rebuild** (`npx expo run:android` / `eas build`); restarting Metro is not enough.
- **Web:** static map images fail (and now show an explicit fallback message instead of an
  invisible broken image) when the key lacks the **Maps Static API** or its restrictions
  exclude your site. Key restrictions for web must be **HTTP referrer** based (an
  Android-app-restricted key will NOT serve static maps to a browser — use a second key for
  web if you restrict by platform).

## Runtime: Expo Go vs development build

- **Web** works today (`npm run web`) — good for a quick UI demo.
- **Expo Go** must be updated to the version that supports **SDK 56** (Play Store / App Store).
  Note Expo Go **ignores custom native config**, so a custom Google Maps key, push
  notifications, and background sync are **not** available in Expo Go (Android Expo Go can show
  maps with Expo's own key; iOS Expo Go uses Apple Maps).
- For **full** Google Maps + notifications + background sync, build a **development build**:
  `npx expo run:android` (needs Android Studio) or an EAS build. This is the correct runtime
  for the finished app.

## Production builds (EAS)

Build profiles live in `eas.json` (`development` / `preview` / `production`). One-time setup:

```bash
npm install -g eas-cli
eas login                    # Expo account
cd mobile
eas init                     # links the app; writes extra.eas.projectId into app.json
```

Give EAS the Google Maps key so it is inlined at build time (EXPO_PUBLIC_* variables must be
visible to the bundler — create it as a plain/sensitive env var, not "secret"):

```bash
eas env:create --name EXPO_PUBLIC_GOOGLE_MAPS_API_KEY --value <your-key> \
  --environment production --environment preview --environment development
```

Then build:

```bash
eas build --profile development --platform android   # dev client APK (install + `npm start`)
eas build --profile preview --platform android       # shareable internal APK
eas build --profile production --platform android    # Play Store .aab (versionCode auto-increments)
eas build --profile production --platform ios        # App Store (needs Apple Developer account)
```

Notes:

- **Identifiers:** `com.ebads.dispatcher` (both platforms, set in `app.json`).
- **Google Maps key restrictions** (Google Cloud console → the key → Application restrictions):
  restrict to Android app `com.ebads.dispatcher` with the SHA-1 shown by
  `eas credentials -p android`, and to iOS bundle id `com.ebads.dispatcher`. Enable
  **Maps SDK for Android**, **Maps SDK for iOS**, **Maps Static API** (web), and
  **Directions API** (live in-app navigation route, `services/directions.ts`).
- **Cleartext HTTP:** the engine is plain `http://` on a LAN, and Android release builds block
  cleartext by default — `expo-build-properties` sets `usesCleartextTraffic: true` in
  `app.json`. Remove that once the engine is served over HTTPS.
- **Versioning:** `appVersionSource: remote` + `autoIncrement` — EAS bumps
  `versionCode`/`buildNumber` on each production build; bump the human-readable `version` in
  `app.json` yourself per release.
- Local alternative (no EAS account): `npx expo prebuild` then `npx expo run:android --variant release`
  with Android Studio installed.

## Connect to the engine

The app talks to the FastAPI engine (docs/04) over a signed-in, bearer-token session
(EBADS_PRD.md §10) — dispatcher accounts are created by a system_administrator (web portal or
`scripts/create_system_admin.py`), then sign in from **`LoginScreen`**, the app's first
screen once onboarding is done. There is no "API key" anymore (retired, Increment 1) and no
editable base-URL field in Settings — the engine address is a **build-time** env var, set
once per build/environment, not typed by the dispatcher:

- **`EXPO_PUBLIC_ENGINE_BASE_URL`** in `.env` (copy from `.env.example`), including the
  `/api/v1` prefix — e.g. `https://ebads-engine-vyun.onrender.com/api/v1` for production, or
  `http://192.168.x.x:8000/api/v1` (your machine's LAN IP) for a local engine on a physical
  device/Android emulator (`localhost` works for web/iOS simulator only). Start the local
  engine so it listens on all interfaces (`docker compose -f infra/docker-compose.yml up`).
- For an **EAS cloud build**, set the same variable in the EAS project's per-environment
  variables (dashboard, or `eas env:create`) — a local `.env` is read for `expo start`/local
  builds but not automatically picked up by `eas build`, the same way
  `EXPO_PUBLIC_GOOGLE_MAPS_API_KEY` already works.
- Settings still has a **"Test connection"** button — it re-probes the fixed URL's
  `/healthz` and shows the verdict, useful for "is the engine actually up right now", not for
  reconfiguring anything.
- **Android maps + live navigation** need the Google Maps API key from `.env` —
  `app.config.js` injects `EXPO_PUBLIC_GOOGLE_MAPS_API_KEY` into the native config at build
  time. Enable **Directions API** alongside Maps SDK/Maps Static API for the in-app
  turn-by-turn route (`services/directions.ts`) to work; without it, navigation falls back to
  a straight line and Haversine-estimated distance/ETA.

## Layout (docs/05 §7)

```
src/
  theme/        design tokens + type scale (from the UI design system)
  components/   shared UI (AppText, Card, Button, AppBar, Screen, OfflineBanner…)
  services/     api, cache (SQLite), sync, connectivity, storage
  state/        Settings / Connectivity / Sync contexts
  navigation/   bottom tabs
  screens/      Dispatch, FacilityMap, Simulation, Settings
```
