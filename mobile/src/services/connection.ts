/**
 * Engine reachability test — one explicit, user-triggered probe of the configured URL.
 *
 * Used by Settings ("Save & test") and the onboarding connect step. It verifies, in order: the
 * URL parses, and the engine's public health endpoint answers — and returns a precise, human-
 * actionable verdict. This is a pure reachability probe, unauthenticated by design: it runs
 * before a dispatcher has necessarily signed in, and every other route requires a bearer token
 * (EBADS_PRD.md §10) that only `POST /auth/login` on `LoginScreen` can obtain. A wrong password
 * is a login failure, not a connection failure — they are diagnosed in two different places on
 * purpose, matching where the dispatcher can actually act on each (docs/05 §5).
 */

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

/** Trim + drop trailing slashes so `http://host:8000/api/v1/` equals `…/api/v1`. */
export function normalizeBaseUrl(input: string): string {
  return input.trim().replace(/\/+$/, '');
}

/** Parse an absolute http(s) URL, or null when the text is not one. */
function parseHttpUrl(value: string): URL | null {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url : null;
  } catch {
    return null;
  }
}

/** Run the full probe against the given base URL (NOT necessarily the currently saved one). */
export async function testConnection(baseUrl: string): Promise<ConnectionTestResult> {
  const normalized = normalizeBaseUrl(baseUrl);
  const url = parseHttpUrl(normalized);
  if (!url) {
    return {
      ok: false,
      stage: 'url',
      message:
        'Enter the full engine URL including http:// or https://, e.g. http://192.168.1.10:8000/api/v1.',
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
          'Reached the server, but there is no EBADS API at this path — the base URL should end with /api/v1.',
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
      message:
        'Could not reach the engine. Check the URL, your network, and that the engine is running.',
    };
  } finally {
    clearTimeout(timer);
  }
}
