import { readMe } from "@directus/sdk";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Spinner } from "@/components/ui";
import { getMe } from "@/lib/api";
import type { CallerRole, Me } from "@/lib/api";
import { authStorage } from "@/lib/auth-storage";
import { directus } from "@/lib/directus";

import { AuthContext, callerRole, homePath } from "./auth-context";
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

// Which view the signed-in user gets is the app's answer, not Directus's, so it comes
// from /api/me. A failure here must not lock a tutor out of an app that worked before
// the endpoint existed: `null` means "we could not ask", and `callerRole` reads that as
// a tutor.
async function fetchIdentity(): Promise<Me | null> {
  try {
    return await getMe();
  } catch {
    return null;
  }
}

// Only Directus rejecting the token means the stored session is worthless. A request
// that never got an answer — a reload landing while the check is still in flight, or
// Directus briefly unreachable — must leave the stored session alone, or a refresh at
// the wrong moment would sign the user out.
function isRejectedSession(error: unknown): boolean {
  const response = (error as { response?: { status?: number } } | null)?.response;
  return response?.status === 401 || response?.status === 403;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [me, setMe] = useState<Me | null>(null);
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
        const identity = await fetchIdentity();
        if (!cancelled) {
          setUser(restored);
          setMe(identity);
        }
      } catch (error) {
        if (isRejectedSession(error)) {
          await authStorage.set(null);
        }
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
    // `me` before `user`: a route guard runs as soon as `user` is set, and it must not
    // see a signed-in caller whose role is still unknown.
    setMe(await fetchIdentity());
    setUser(await fetchUser());
  }, []);

  const logout = useCallback(async () => {
    try {
      await directus.logout();
    } finally {
      await authStorage.set(null);
      setUser(null);
      setMe(null);
      queryClient.clear();
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, me, isAuthenticated: user !== null, isChecking, login, logout }),
    [user, me, isChecking, login, logout]
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

/**
 * Keeps the two views apart: a student who asks for a tutor route lands on `/me`, and a
 * tutor who asks for `/me` lands on `/`. Wrap it inside `RequireAuth`, which is what
 * guarantees there is a caller to have a role at all.
 */
export function RequireRole({ role, children }: { role: CallerRole; children: ReactNode }) {
  const { me } = useAuth();
  const actual = callerRole(me);

  if (actual !== role) {
    return <Navigate to={homePath(me)} replace />;
  }

  return children;
}
