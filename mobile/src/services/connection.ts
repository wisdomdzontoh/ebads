/**
 * Engine reachability test — one explicit, user-triggered probe of the fixed, build-time
 * `ENGINE_BASE_URL` (services/env.ts) — there is nothing left to mistype, so this exists purely
 * to catch "the engine happens to be down / no network right now" early and precisely, rather
 * than as a way to point the app somewhere else.
 *
 * Used by Settings ("Test connection") and the onboarding connect step. Verifies, in order:
 * the configured URL parses, and the engine's public health endpoint answers — and returns a
 * precise, human-actionable verdict. This is a pure reachability probe, unauthenticated by
 * design: it can run before a dispatcher has signed in, and every other route requires a
 * bearer token (EBADS_PRD.md §10) that only `POST /auth/login` on `LoginScreen` can obtain. A
 * wrong password is a login failure, not a connection failure — they are diagnosed in two
 * different places on purpose, matching where the dispatcher can actually act on each (docs/05
 * §5).
 */

import { ENGINE_BASE_URL } from './env';

const TEST_TIMEOUT_MS = 10_000;

export interface ConnectionOk {
  ok: true;
}

export interface ConnectionFailed {
  ok: false;
  /** Which layer failed, so the UI can point at the exact field to fix. */
  stage: 'url' | 'network' | 'endpoint' | 'server';
  message: string;
}

export type ConnectionTestResult = ConnectionOk | ConnectionFailed;

/** Parse an absolute http(s) URL, or null when the text is not one. */
function parseHttpUrl(value: string): URL | null {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url : null;
  } catch {
    return null;
  }
}

/** Run the full probe against `ENGINE_BASE_URL`. A malformed `stage: 'url'` result here means
 * the build itself is misconfigured (EXPO_PUBLIC_ENGINE_BASE_URL), not something the
 * dispatcher can fix in the app. */
export async function testConnection(): Promise<ConnectionTestResult> {
  const url = parseHttpUrl(ENGINE_BASE_URL);
  if (!url) {
    return {
      ok: false,
      stage: 'url',
      message:
        'The app is misconfigured: EXPO_PUBLIC_ENGINE_BASE_URL is not a valid http(s) URL. This needs a new build, not a Settings change.',
    };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${url.origin}/healthz`, { signal: controller.signal });
    if (response.ok) return { ok: true };
    if (response.status === 404) {
      return {
        ok: false,
        stage: 'endpoint',
        message:
          'Reached the server, but there is no EBADS API at this path — the app is misconfigured (needs a new build).',
      };
    }
    return {
      ok: false,
      stage: 'server',
      message: `The engine answered with an error (HTTP ${response.status}). Check the engine logs.`,
    };
  } catch {
    return {
      ok: false,
      stage: 'network',
      message: 'Could not reach the engine. Check your network and that the engine is running.',
    };
  } finally {
    clearTimeout(timer);
  }
}
