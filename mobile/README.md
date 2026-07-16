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
  **Maps SDK for Android**, **Maps SDK for iOS**, and **Maps Static API** (web).
- **Cleartext HTTP:** the engine is plain `http://` on a LAN, and Android release builds block
  cleartext by default — `expo-build-properties` sets `usesCleartextTraffic: true` in
  `app.json`. Remove that once the engine is served over HTTPS.
- **Versioning:** `appVersionSource: remote` + `autoIncrement` — EAS bumps
  `versionCode`/`buildNumber` on each production build; bump the human-readable `version` in
  `app.json` yourself per release.
- Local alternative (no EAS account): `npx expo prebuild` then `npx expo run:android --variant release`
  with Android Studio installed.

## Connect to the engine

The app talks to the FastAPI engine (docs/04). Configure the base URL in **Settings**
(default `http://localhost:8000/api/v1`).

- **API key:** Settings → "API key" must hold the exact `API_KEY` value from `infra/.env`
  (any static string works — e.g. `openssl rand -hex 32`; it is a shared secret, not a
  format). The engine rejects `/api/v1` requests without it (401). If `API_KEY` is blank
  the engine skips the check, and the app field can stay empty too.

- **Web / iOS simulator:** `localhost` works.
- **Physical device / Android emulator:** use your machine's LAN IP, e.g.
  `http://192.168.x.x:8000/api/v1`, and start the engine so it listens on all interfaces
  (`docker compose -f infra/docker-compose.yml up`).
- **Android maps** need the Google Maps API key from `.env` — `app.config.js` injects
  `EXPO_PUBLIC_GOOGLE_MAPS_API_KEY` into the native config at build time.

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
