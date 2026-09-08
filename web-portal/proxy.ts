import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// UX-level route gating only — checks cookie *presence*, not validity. The FastAPI backend
// (app/security/dependencies.py::require_permission) remains the sole real enforcement
// point for every request the browser makes directly to it.
//
// Gates on the REFRESH token cookie (7-day lifetime), not the access token (30 min) — the
// access token cookie naturally expires after any 30-minute gap in activity even though the
// session is still perfectly valid; gating on it here redirected to /login at the EDGE, before
// the client ever got a chance to run its own silent refresh-on-401 (lib/api-client.ts), so a
// short idle period forced a full re-login regardless of how much of the 7-day session
// remained. The refresh token is the one that actually determines whether the session is
// still alive.
const REFRESH_TOKEN_COOKIE = "ebads_refresh_token";
const PUBLIC_ROUTES = new Set(["/login"]);

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAuthenticated = request.cookies.has(REFRESH_TOKEN_COOKIE);

  if (pathname === "/") {
    return NextResponse.redirect(
      new URL(isAuthenticated ? "/dashboard" : "/login", request.url)
    );
  }

  if (PUBLIC_ROUTES.has(pathname)) {
    return isAuthenticated
      ? NextResponse.redirect(new URL("/dashboard", request.url))
      : NextResponse.next();
  }

  if (!isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  // icon.png (and any sibling apple-icon/opengraph-image/robots.txt/sitemap.xml Next.js
  // file-convention metadata routes) are always public — browsers request them
  // unauthenticated, so gating them behind login would just serve a broken favicon.
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|icon\\.png|apple-icon\\.png|opengraph-image|robots\\.txt|sitemap\\.xml).*)",
  ],
};
