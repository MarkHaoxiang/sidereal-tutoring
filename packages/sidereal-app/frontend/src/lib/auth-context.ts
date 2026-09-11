import { createContext, useContext } from "react";

export interface AuthUser {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
}

export interface AuthContextValue {
  user: AuthUser | null;
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

export function userDisplayName(user: AuthUser | null): string {
  if (!user) {
    return "";
  }
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email || "Signed in";
}
