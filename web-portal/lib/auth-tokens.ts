"use client";

// Client-readable (non-httpOnly) cookies: the portal calls the FastAPI backend directly
// from the browser (see lib/env.ts), and proxy.ts needs to read the same cookies at the
// edge for route-gating, so httpOnly is not an option here. Real enforcement always
// happens on the backend via require_permission — these cookies only drive client UX.
import type { Role, TokenResponse } from "./types";

const ACCESS_TOKEN_COOKIE = "ebads_access_token";
const REFRESH_TOKEN_COOKIE = "ebads_refresh_token";
const ROLE_COOKIE = "ebads_role";
const FACILITY_ID_COOKIE = "ebads_facility_id";

// Mirrors backend/app/parameters.py ACCESS_TOKEN_TTL_MIN / REFRESH_TOKEN_TTL_DAYS — the
// cookie's outer lifetime tracks the token's actual validity window.
const ACCESS_TOKEN_MAX_AGE_SEC = 30 * 60;
const REFRESH_TOKEN_MAX_AGE_SEC = 7 * 24 * 60 * 60;

export const AUTH_COOKIE_NAMES = {
  accessToken: ACCESS_TOKEN_COOKIE,
  refreshToken: REFRESH_TOKEN_COOKIE,
  role: ROLE_COOKIE,
  facilityId: FACILITY_ID_COOKIE,
} as const;

export interface StoredSession {
  accessToken: string;
  refreshToken: string;
  role: Role;
  facilityId: string | null;
}

function setCookie(name: string, value: string, maxAgeSec: number) {
  const secure =
    typeof window !== "undefined" && window.location.protocol === "https:"
      ? "; Secure"
      : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAgeSec}; SameSite=Lax${secure}`;
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name}=([^;]*)`)
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function clearCookie(name: string) {
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function storeSession(tokens: TokenResponse) {
  setCookie(ACCESS_TOKEN_COOKIE, tokens.access_token, ACCESS_TOKEN_MAX_AGE_SEC);
  setCookie(REFRESH_TOKEN_COOKIE, tokens.refresh_token, REFRESH_TOKEN_MAX_AGE_SEC);
  setCookie(ROLE_COOKIE, tokens.role, REFRESH_TOKEN_MAX_AGE_SEC);
  if (tokens.facility_id) {
    setCookie(FACILITY_ID_COOKIE, tokens.facility_id, REFRESH_TOKEN_MAX_AGE_SEC);
  } else {
    clearCookie(FACILITY_ID_COOKIE);
  }
}

export function storeAccessToken(accessToken: string) {
  setCookie(ACCESS_TOKEN_COOKIE, accessToken, ACCESS_TOKEN_MAX_AGE_SEC);
}

export function readSession(): StoredSession | null {
  const accessToken = getCookie(ACCESS_TOKEN_COOKIE);
  const refreshToken = getCookie(REFRESH_TOKEN_COOKIE);
  const role = getCookie(ROLE_COOKIE) as Role | null;
  if (!accessToken || !refreshToken || !role) return null;
  return { accessToken, refreshToken, role, facilityId: getCookie(FACILITY_ID_COOKIE) };
}

export function clearSession() {
  clearCookie(ACCESS_TOKEN_COOKIE);
  clearCookie(REFRESH_TOKEN_COOKIE);
  clearCookie(ROLE_COOKIE);
  clearCookie(FACILITY_ID_COOKIE);
}
