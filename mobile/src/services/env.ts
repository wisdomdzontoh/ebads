/**
 * The EBADS engine's base URL — a build-time constant, not a dispatcher-editable setting.
 *
 * Previously a free-text field in Settings/onboarding; dropped because (a) there is exactly
 * one engine a given build should ever talk to — production dispatchers have no reason to
 * repoint the app, and a mistyped URL was a support burden with no upside — and (b) it mirrors
 * `EXPO_PUBLIC_GOOGLE_MAPS_API_KEY` (services/maps.ts), which was already build-time-only.
 * Set per EAS build profile (the EAS dashboard's per-environment variables, or `eas.json`'s
 * "env" block) so a preview build and a production build can point at different engines
 * without a code change — see `.env.example`.
 */

const RAW = process.env.EXPO_PUBLIC_ENGINE_BASE_URL ?? 'http://localhost:8000/api/v1';

/** No trailing slash, so every caller can safely do `${ENGINE_BASE_URL}/path`. */
export const ENGINE_BASE_URL: string = RAW.trim().replace(/\/+$/, '');
