import { API_BASE_URL } from "./env";
import { clearSession, readSession, storeAccessToken } from "./auth-tokens";
import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, message: string, body: ApiErrorBody | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function errorMessage(body: ApiErrorBody | null, fallback: string): string {
  if (!body?.detail) return fallback;
  if (typeof body.detail === "string") return body.detail;
  return body.detail.map((e) => e.msg).join("; ") || fallback;
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Attach the stored bearer token and retry once on 401 via refresh. Default true. */
  auth?: boolean;
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { access_token: string };
  storeAccessToken(data.access_token);
  return data.access_token;
}

// Single-flight: concurrent 401s from several in-flight requests share one refresh call
// instead of each racing their own POST /auth/refresh.
function refreshOnce(refreshToken: string): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = refreshAccessToken(refreshToken).finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { body, auth = true, headers, ...rest } = options;
  const session = auth ? readSession() : null;

  const doFetch = (accessToken: string | null) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  let res = await doFetch(session?.accessToken ?? null);

  if (res.status === 401 && auth && session?.refreshToken) {
    const newAccessToken = await refreshOnce(session.refreshToken);
    if (newAccessToken) {
      res = await doFetch(newAccessToken);
    } else {
      clearSession();
    }
  }

  if (!res.ok) {
    const parsed = (await parseBody(res)) as ApiErrorBody | null;
    throw new ApiError(res.status, errorMessage(parsed, res.statusText), parsed);
  }

  return (await parseBody(res)) as T;
}
