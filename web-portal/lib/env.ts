// Base URL of the EBADS engine API (docs/01-architecture.md §4). Must be NEXT_PUBLIC_-
// prefixed since the portal calls the backend directly from the browser (no BFF proxy
// layer) — see components/auth-provider.tsx for why.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
