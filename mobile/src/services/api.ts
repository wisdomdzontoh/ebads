/**
 * Engine API client — the app's only channel to the allocation engine (docs/04-api-spec.md).
 *
 * A thin, typed `fetch` wrapper: it sends requests and deserialises typed responses, and does
 * NOTHING else. All matching decisions (recommendation, escalation, scores) come back from the
 * engine already computed (docs/05 §8); this client never scores, filters, or ranks.
 *
 * Auth (EBADS_PRD.md §10): every route but `/auth/login` and `/auth/refresh` requires a bearer
 * access token — the retired `X-API-Key` scheme is gone from the backend entirely (Increment 1),
 * so this client never sends it. `getAccessToken`/`onUnauthorized` are injected by
 * `state/AuthContext.tsx`, which owns the actual token state; this class only knows how to ASK
 * for a token and how to react to a 401 (retry once after a caller-supplied refresh, then give
 * up and let the 401 propagate so the caller can force a sign-out). A request the caller marks
 * `auth: false` (login, refresh) never attaches a token and never triggers a refresh.
 */

import type {
  AccessTokenResponse,
  AllocationAuditRead,
  AllocationRequest,
  AllocationResponse,
  AllocationStatus,
  Facility,
  LoginRequest,
  PasswordChangeRequest,
  ReallocateRequest,
  RunSummary,
  SimulationSessionCreate,
  SimulationSessionRead,
  StepTrace,
  TokenResponse,
} from './types';

/** Raised for any non-2xx response or transport failure; carries the HTTP status (0 = network). */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ApiConfig {
  /** Full base URL up to and including the version prefix, e.g. `http://host:8000/api/v1`. */
  baseUrl: string;
  timeoutMs?: number;
  /** Returns the current access token, or null when signed out. Read fresh on every request. */
  getAccessToken?: () => string | null;
  /** Called once on a 401 from an `auth`-required request; returns the new access token (already
   * persisted by the caller) or null if refresh itself failed — a null lets the original 401
   * propagate as `ApiError` instead of retrying forever. */
  onUnauthorized?: () => Promise<string | null>;
}

const DEFAULT_TIMEOUT_MS = 12000;

/** Pull the most useful human message out of an engine error body (FastAPI `detail`). */
function extractDetail(body: unknown): string | null {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    // FastAPI 422 validation errors are an array of {loc, msg, type} — surface the messages,
    // not the raw JSON structure.
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : JSON.stringify(item),
        )
        .join('; ');
    }
  }
  return null;
}

interface RequestOptions extends RequestInit {
  /** Attach the bearer token and retry once via `onUnauthorized` on a 401. Default true. */
  auth?: boolean;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly getAccessToken: () => string | null;
  private readonly onUnauthorized: (() => Promise<string | null>) | null;

  constructor(config: ApiConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, ''); // no trailing slash
    this.timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.getAccessToken = config.getAccessToken ?? (() => null);
    this.onUnauthorized = config.onUnauthorized ?? null;
  }

  /** Issue one request with a timeout, returning the parsed JSON body typed as `T`. */
  private async request<T>(path: string, init?: RequestOptions): Promise<T> {
    const { auth = true, headers, ...rest } = init ?? {};

    const doFetch = async (token: string | null): Promise<Response> => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      try {
        return await fetch(`${this.baseUrl}${path}`, {
          ...rest,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
            ...headers,
          },
        });
      } finally {
        clearTimeout(timer);
      }
    };

    try {
      let response = await doFetch(auth ? this.getAccessToken() : null);

      if (response.status === 401 && auth && this.onUnauthorized) {
        const refreshed = await this.onUnauthorized();
        if (refreshed) {
          response = await doFetch(refreshed);
        }
      }

      const text = await response.text();
      // A proxy/gateway can return non-JSON (HTML) error pages — never let a parse failure
      // mask the real HTTP status.
      let body: unknown = null;
      if (text) {
        try {
          body = JSON.parse(text);
        } catch {
          body = null;
        }
      }
      if (!response.ok) {
        throw new ApiError(response.status, extractDetail(body) ?? response.statusText);
      }
      return body as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      // AbortError (timeout) and network failures both surface as status 0, with a message a
      // dispatcher can act on rather than a raw runtime string.
      const message =
        error instanceof Error && error.name === 'AbortError'
          ? 'Request timed out — check the engine URL in Settings.'
          : 'Could not reach the engine — check connectivity and the engine URL in Settings.';
      throw new ApiError(0, message);
    }
  }

  // --- auth (EBADS_PRD.md §10) ----------------------------------------------

  /** Unauthenticated — email/password in, an access/refresh token pair out. */
  login(body: LoginRequest): Promise<TokenResponse> {
    return this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
      auth: false,
    });
  }

  /** Unauthenticated — a valid refresh token in, a fresh access token out. */
  refreshAccessToken(refreshToken: string): Promise<AccessTokenResponse> {
    return this.request<AccessTokenResponse>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
      auth: false,
    });
  }

  /** Self-service password change, the caller's own account (204 No Content). */
  async changePassword(body: PasswordChangeRequest): Promise<void> {
    await this.request<null>('/auth/password', { method: 'PATCH', body: JSON.stringify(body) });
  }

  // --- facilities ------------------------------------------------------------

  /** List all facilities; `updatedSince` (ISO-8601) fetches only changed rows (docs/04 §3). */
  getFacilities(updatedSince?: string): Promise<Facility[]> {
    const query = updatedSince ? `?updated_since=${encodeURIComponent(updatedSince)}` : '';
    return this.request<Facility[]>(`/facilities${query}`);
  }

  // --- allocations (docs/01 §7, FR8-FR11, FR20, FR22, FR24-27) ---------------

  /** Submit an emergency; the engine returns a recommendation or a structured escalation. */
  createAllocation(body: AllocationRequest): Promise<AllocationResponse> {
    return this.request<AllocationResponse>('/allocations', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** Fetch one of the dispatcher's own allocations — used to poll a confirmed reservation for
   * a status change (arrival elsewhere, or revocation) since there is no real push channel. */
  getAllocation(allocationId: string): Promise<AllocationAuditRead> {
    return this.request<AllocationAuditRead>(`/allocations/${allocationId}`);
  }

  /** List the dispatcher's own allocations, newest first; optionally filtered by status. */
  listAllocations(statusFilter?: AllocationStatus): Promise<AllocationAuditRead[]> {
    const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
    return this.request<AllocationAuditRead[]>(`/allocations${query}`);
  }

  /** FR22: confirm the patient arrived — converts the reservation to an admission. Only the
   * dispatcher who submitted the request may do this (docs/01 §7). */
  recordArrival(allocationId: string): Promise<AllocationAuditRead> {
    return this.request<AllocationAuditRead>(`/allocations/${allocationId}/arrive`, {
      method: 'POST',
    });
  }

  /** FR24-27: re-run the allocation engine from the dispatcher's CURRENT position after the
   * facility revoked the original reservation (or it escalated) — same engine, a different
   * origin; the revoking facility is excluded from the new candidates automatically. */
  reallocate(allocationId: string, body: ReallocateRequest): Promise<AllocationResponse> {
    return this.request<AllocationResponse>(`/allocations/${allocationId}/reallocate`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  // --- simulation (research/demo surface, docs/04 §5 — not part of live dispatch) -----------

  createSimulationSession(body: SimulationSessionCreate): Promise<SimulationSessionRead> {
    return this.request<SimulationSessionRead>('/simulation/sessions', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  runSimulation(sessionId: string): Promise<RunSummary> {
    return this.request<RunSummary>(`/simulation/sessions/${sessionId}/run`, { method: 'POST' });
  }

  stepSimulation(sessionId: string): Promise<StepTrace> {
    return this.request<StepTrace>(`/simulation/sessions/${sessionId}/step`, { method: 'POST' });
  }

  getSimulationSession(sessionId: string): Promise<SimulationSessionRead> {
    return this.request<SimulationSessionRead>(`/simulation/sessions/${sessionId}`);
  }
}
