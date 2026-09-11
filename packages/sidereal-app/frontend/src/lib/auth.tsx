import { readMe } from "@directus/sdk";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Spinner } from "@/components/ui";
import { authStorage } from "@/lib/auth-storage";
import { directus } from "@/lib/directus";

import { AuthContext } from "./auth-context";
import type { AuthUser } from "./auth-context";
import { useAuth } from "./auth-context";
import styles from "./auth.module.css";

const USER_FIELDS = ["id", "first_name", "last_name", "email"] as const;

async function fetchUser(): Promise<AuthUser> {
  const me = await directus.request(readMe({ fields: [...USER_FIELDS] }));
  return {
    id: me.id,
    first_name: me.first_name ?? null,
    last_name: me.last_name ?? null,
    email: me.email ?? null,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  // A stored session has to be confirmed against Directus before anything renders a
  // redirect, or a reload would bounce a signed-in tutor to /login.
  useEffect(() => {
    let cancelled = false;

    const restore = async () => {
      try {
        const stored = await authStorage.get();
        if (!stored?.access_token && !stored?.refresh_token) {
          return;
        }
        const restored = await fetchUser();
        if (!cancelled) {
          setUser(restored);
        }
      } catch {
        await authStorage.set(null);
      } finally {
        if (!cancelled) {
          setIsChecking(false);
        }
      }
    };

    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await directus.login({ email, password });
    setUser(await fetchUser());
  }, []);

  const logout = useCallback(async () => {
    try {
      await directus.logout();
    } finally {
      await authStorage.set(null);
      setUser(null);
      queryClient.clear();
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, isAuthenticated: user !== null, isChecking, login, logout }),
    [user, isChecking, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isChecking } = useAuth();
  const location = useLocation();

  if (isChecking) {
    return (
      <div className={styles.checking}>
        <Spinner size="lg" label="Checking your sign-in" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
