import { useCallback, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { directus } from "@/lib/directus";

import { AuthContext, useAuth } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  // Directus's own `authentication('json')` client holds the token in memory only —
  // this flag mirrors that lifetime deliberately: a reload logs the tutor out, same
  // as the SDK's storage does, rather than us persisting anything of our own.
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const login = useCallback(async (email: string, password: string) => {
    await directus.login({ email, password });
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(async () => {
    try {
      await directus.logout();
    } finally {
      setIsAuthenticated(false);
    }
  }, []);

  const value = useMemo(() => ({ isAuthenticated, login, logout }), [isAuthenticated, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
