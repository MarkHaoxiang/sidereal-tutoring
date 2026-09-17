import { createContext, useContext } from "react";

import type { CallerRole, Me } from "@/lib/api";
import type { Appearance } from "@/lib/theme";

export interface AuthUser {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  avatar: string | null;
  /** Null until they choose one, which follows the device exactly as "auto" does. */
  appearance: Appearance | null;
}

export interface AuthContextValue {
  user: AuthUser | null;
  /** GET /api/me for the signed-in user, fetched once per session; null if it failed. */
  me: Me | null;
  isAuthenticated: boolean;
  /** The stored session is still being checked; nothing may redirect to /login yet. */
  isChecking: boolean;
  /** The app refused the caller the stored session belonged to, so they were signed out. */
  refused: boolean;
  login: (email: string, password: string) => Promise<Me | null>;
  logout: () => Promise<void>;
  /** Re-reads the signed-in user, so a saved name or photo reaches the shell. */
  refreshUser: () => Promise<void>;
}

/** What a caller refused after signing in is told, whatever refused them. */
export const SIGNED_OUT = "You have been signed out. Sign in to continue.";

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

// Three surfaces behind one login. An unreachable /api/me leaves `me` null, and the tutor
// app is what this app has always been, so that is the fallback.
export function callerRole(me: Me | null): CallerRole {
  return me?.role ?? "tutor";
}

/** Where a signed-in caller lands: `/admin`, `/me`, or the tutor app at `/`. */
export function homePath(me: Me | null): string {
  const role = callerRole(me);
  if (role === "student") {
    return "/me";
  }
  return role === "admin" ? "/admin" : "/";
}

/**
 * Whether a caller may open a surface. An admin runs the practice, so the tutor app is
 * theirs too — they see every student, since admin bypasses Directus's row filters. The
 * student view and the admin surface admit their own role and nobody else.
 */
export function roleAdmits(surface: CallerRole, actual: CallerRole): boolean {
  if (surface === "tutor") {
    return actual === "tutor" || actual === "admin";
  }
  return actual === surface;
}

export function userDisplayName(user: AuthUser | null): string {
  if (!user) {
    return "";
  }
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email || "Signed in";
}
