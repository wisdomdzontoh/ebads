"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api-client";
import { clearSession, readSession, storeSession } from "@/lib/auth-tokens";
import type { LoginRequest, Role, TokenResponse } from "@/lib/types";

interface AuthUser {
  role: Role;
  facilityId: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Cookies are only readable client-side, so the session is hydrated after mount rather
  // than in a useState initializer — computing it eagerly would render different content
  // on the server (no cookies) vs. the client on first paint, causing a hydration mismatch.
  useEffect(() => {
    const session = readSession();
    // One-time sync from the cookie store (an external system) at mount; deferring to
    // isLoading avoids the SSR hydration mismatch this rule normally guards against.
    /* eslint-disable-next-line react-hooks/set-state-in-effect */
    setUser(session ? { role: session.role, facilityId: session.facilityId } : null);
    setIsLoading(false);
  }, []);

  const login = useCallback(async ({ email, password }: LoginRequest) => {
    const tokens = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    storeSession(tokens);
    setUser({ role: tokens.role, facilityId: tokens.facility_id });
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
