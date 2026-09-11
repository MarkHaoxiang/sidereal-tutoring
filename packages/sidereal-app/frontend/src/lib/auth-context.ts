import { createContext, useContext } from "react";

import type { CallerRole, Me } from "@/lib/api";

export interface AuthUser {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
}

export interface AuthContextValue {
  user: AuthUser | null;
  /** GET /api/me for the signed-in user, fetched once per session; null if it failed. */
  me: Me | null;
  isAuthenticated: boolean;
  /** The stored session is still being checked; nothing may redirect to /login yet. */
  isChecking: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

// Undefined outside a provider, so `useAuth` can tell "no provider" apart from
// "provider says logged out".
export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

// A student sees the student view and nothing else; everyone else — tutors and admins —
// sees the tutor app. An unreachable /api/me leaves `me` null, and the tutor app is what
// this app has always been, so that is the fallback.
export function callerRole(me: Me | null): CallerRole {
  return me?.role ?? "tutor";
}

/** Where a signed-in caller belongs: the student view is under `/me`. */
export function homePath(me: Me | null): string {
  return callerRole(me) === "student" ? "/me" : "/";
}

export function userDisplayName(user: AuthUser | null): string {
  if (!user) {
    return "";
  }
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email || "Signed in";
}
