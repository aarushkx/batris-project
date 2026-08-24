"use client";

import * as React from "react";
import { API_ROUTES } from "@/lib/constants";
import { ApiError } from "@/lib/api";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (name: string, email: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

async function authRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* ignore empty response bodies */
  }
  if (!response.ok) {
    const detail =
      (body as { error?: string; detail?: string } | null)?.error ??
      (body as { error?: string; detail?: string } | null)?.detail ??
      `Request failed with status ${response.status}`;
    throw new ApiError(detail, response.status);
  }
  return body as T;
}

export async function saveAssessmentHistory(payload: {
  battery_id?: string | null;
  input_mode: string;
  format_key?: string | null;
  input_snapshot: Record<string, unknown>;
  assessment: unknown;
}) {
  return authRequest<{ saved: boolean }>(API_ROUTES.accountAssessments, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function savePassportHistory(passport: unknown) {
  return authRequest<{ saved: boolean }>(API_ROUTES.accountPassports, {
    method: "POST",
    body: JSON.stringify({ passport }),
  });
}

export async function getAccountHistory() {
  const [assessments, passports] = await Promise.all([
    authRequest<{ items: Array<Record<string, any>> }>(API_ROUTES.accountAssessments),
    authRequest<{ items: Array<Record<string, any>> }>(API_ROUTES.accountPassports),
  ]);
  return { assessments: assessments.items, passports: passports.items };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<AuthUser | null>(null);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    try {
      const result = await authRequest<{ user: AuthUser | null }>(API_ROUTES.authMe);
      setUser(result.user);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      refresh,
      async login(email, password) {
        const result = await authRequest<{ user: AuthUser }>(API_ROUTES.authLogin, {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        setUser(result.user);
        return result.user;
      },
      async register(name, email, password) {
        const result = await authRequest<{ user: AuthUser }>(API_ROUTES.authRegister, {
          method: "POST",
          body: JSON.stringify({ name, email, password }),
        });
        setUser(result.user);
        return result.user;
      },
      async logout() {
        await authRequest<{ ok: boolean }>(API_ROUTES.authLogout, { method: "POST" });
        setUser(null);
      },
    }),
    [loading, refresh, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = React.useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
