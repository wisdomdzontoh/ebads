/**
 * Engine connection test — one explicit, user-triggered probe of the configured connection.
 *
 * Used by Settings ("Save & test connection") and the onboarding connect step. It verifies, in
 * order: the URL parses, the engine is reachable, the API key is accepted, and the facilities
 * endpoint answers — and returns a precise, human-actionable verdict. Misconfiguration is
 * diagnosed HERE, once, with a confirmation on success, instead of surfacing later as scattered
 * fetch errors on every screen (docs/05 §5). This probes connectivity only; it never matches.
 */

import { ApiClient, ApiError } from './api';

export interface ConnectionOk {
  ok: true;
  /** How many facilities the engine returned — shown as proof the connection really works. */
  facilityCount: number;
}

export interface ConnectionFailed {
  ok: false;
  /** Which layer failed, so the UI can point at the exact field to fix. */
  stage: 'url' | 'network' | 'auth' | 'endpoint' | 'server';
  message: string;
}

export type ConnectionTestResult = ConnectionOk | ConnectionFailed;

const TEST_TIMEOUT_MS = 10_000;

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

/** Probe the engine's public health endpoint (no auth) to tell "server down" from "wrong path". */
async function healthzReachable(origin: string): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${origin}/healthz`, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Run the full probe against the given connection values (NOT the currently saved ones). */
export async function testConnection(
  baseUrl: string,
  apiKey: string,
): Promise<ConnectionTestResult> {
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

  const client = new ApiClient({
    baseUrl: normalized,
    apiKey: apiKey || undefined,
    timeoutMs: TEST_TIMEOUT_MS,
  });

  try {
    const facilities = await client.getFacilities();
    return { ok: true, facilityCount: facilities.length };
  } catch (error) {
    if (!(error instanceof ApiError)) {
      return {
        ok: false,
        stage: 'network',
        message: 'Could not reach the engine. Check the URL and your network.',
      };
    }
    if (error.status === 401 || error.status === 403) {
      return {
        ok: false,
        stage: 'auth',
        message:
          'The engine rejected the API key. It must match the key configured on the engine exactly.',
      };
    }
    if (error.status === 404) {
      return {
        ok: false,
        stage: 'endpoint',
        message:
          'Reached the server, but there is no EBADS API at this path — the base URL should end with /api/v1.',
      };
    }
    if (error.status >= 500) {
      return {
        ok: false,
        stage: 'server',
        message: `The engine answered with an error (HTTP ${error.status}). Check the engine logs.`,
      };
    }
    if (error.status === 0) {
      // Transport failure — probe /healthz so the message says WHICH half is broken.
      if (await healthzReachable(url.origin)) {
        return {
          ok: false,
          stage: 'endpoint',
          message:
            'The server is up, but the API path did not answer — the base URL should end with /api/v1.',
        };
      }
      return {
        ok: false,
        stage: 'network',
        message:
          'Could not reach the engine. Check the URL, your network, and that the engine is running.',
      };
    }
    return {
      ok: false,
      stage: 'server',
      message: `Unexpected engine response (HTTP ${error.status}): ${error.message}`,
    };
  }
}
