/**
 * Engine API client — the app's only channel to the allocation engine (docs/04-api-spec.md).
 *
 * A thin, typed `fetch` wrapper: it sends requests and deserialises typed responses, and does
 * NOTHING else. All matching decisions (recommendation, escalation, scores) come back from the
 * engine already computed (docs/05 §8); this client never scores, filters, or ranks. The base
 * URL and optional `X-API-Key` are supplied from Settings, so the dispatcher can point the app
 * at any engine deployment.
 */

import type {
  AllocationRequest,
  AllocationResponse,
  Facility,
  RunSummary,
  SimulationSessionCreate,
  SimulationSessionRead,
  StepTrace,
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
  apiKey?: string;
  timeoutMs?: number;
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

export class ApiClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;

  constructor(config: ApiConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, ''); // no trailing slash
    this.apiKey = config.apiKey;
    this.timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  /** Issue one request with a timeout, returning the parsed JSON body typed as `T`. */
  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(this.apiKey ? { 'X-API-Key': this.apiKey } : {}),
          ...init?.headers,
        },
      });
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
    } finally {
      clearTimeout(timer);
    }
  }

  /** List all facilities; `updatedSince` (ISO-8601) fetches only changed rows (docs/04 §3). */
  getFacilities(updatedSince?: string): Promise<Facility[]> {
    const query = updatedSince ? `?updated_since=${encodeURIComponent(updatedSince)}` : '';
    return this.request<Facility[]>(`/facilities${query}`);
  }

  /** Submit an emergency; the engine returns a recommendation or a structured escalation. */
  createAllocation(body: AllocationRequest): Promise<AllocationResponse> {
    return this.request<AllocationResponse>('/allocations', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

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
