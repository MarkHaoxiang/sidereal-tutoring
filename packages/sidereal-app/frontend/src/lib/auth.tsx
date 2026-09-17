import { readMe } from "@directus/sdk";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { toast } from "sonner";

import { Spinner } from "@/components/ui";
import { ApiError, getMe } from "@/lib/api";
import type { CallerRole, Me } from "@/lib/api";
import { authStorage } from "@/lib/auth-storage";
import { directus } from "@/lib/directus";
import { fileIdOf } from "@/lib/files";
import { saveAppearance } from "@/lib/queries/account";
import { adoptAppearance, setAppearanceWriter } from "@/lib/theme";
import type { Appearance } from "@/lib/theme";

import { AuthContext, SIGNED_OUT, callerRole, homePath, roleAdmits } from "./auth-context";
import type { AuthUser } from "./auth-context";
import { useAuth } from "./auth-context";
import styles from "./auth.module.css";

const USER_FIELDS = ["id", "first_name", "last_name", "email", "avatar", "appearance"] as const;

function asAppearance(value: unknown): Appearance | null {
  return value === "light" || value === "dark" || value === "auto" ? value : null;
}

async function fetchUser(): Promise<AuthUser> {
  const me = await directus.request(readMe({ fields: [...USER_FIELDS] }));
  return {
    id: me.id,
    first_name: me.first_name ?? null,
    last_name: me.last_name ?? null,
    email: me.email ?? null,
    avatar: fileIdOf(me.avatar),
    appearance: asAppearance(me.appearance),
  };
}

/** A caller the app refuses: a login that was removed, suspended, or is nobody's. */
class RefusedSession extends Error {}

// A removed login keeps a token Directus goes on accepting until it expires, and the row
// behind it answers with an id and nothing else. `/api/me` calls a caller it cannot place
// a tutor, so without this the tutor shell is what a removed student would be served.
function isNobody(user: AuthUser): boolean {
  return user.email === null;
}

// Which view the signed-in user gets is the app's answer, not Directus's, so it comes
// from /api/me. An unreachable app must not lock a tutor out of one that worked before
// the endpoint existed: `null` means "we could not ask", and `callerRole` reads that as
// a tutor. A 401 or 403 is not that — it is the app refusing this caller, and a refused
// caller is signed out rather than served the tutor shell by the fallback.
async function fetchIdentity(): Promise<Me | null> {
  try {
    return await getMe();
  } catch (error) {
    if (isRejectedSession(error)) {
      throw new RefusedSession();
    }
    return null;
  }
}

// Only a rejection means the stored session is worthless. A request that never got an
// answer — a reload landing while the check is still in flight, the app or Directus
// briefly unreachable — must leave the stored session alone, or a refresh at the wrong
// moment would sign the user out.
function isRejectedSession(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 401 || error.status === 403;
  }
  const response = (error as { response?: { status?: number } } | null)?.response;
  return response?.status === 401 || response?.status === 403;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [refused, setRefused] = useState(false);

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
        if (isNobody(restored)) {
          throw new RefusedSession();
        }
        const identity = await fetchIdentity();
        if (!cancelled) {
          adoptAppearance(restored.appearance ?? "auto");
          setUser(restored);
          setMe(identity);
        }
      } catch (error) {
        if (error instanceof RefusedSession || isRejectedSession(error)) {
          await authStorage.set(null);
          if (!cancelled) {
            setRefused(true);
          }
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
    setRefused(false);
    // `me` before `user`: a route guard runs as soon as `user` is set, and it must not
    // see a signed-in caller whose role is still unknown. The identity is returned as
    // well, so the login page can send them to their own surface without waiting for
    // this state to reach it. A caller the app refuses keeps no Directus session.
    let identity: Me | null;
    try {
      identity = await fetchIdentity();
    } catch (error) {
      await authStorage.set(null);
      throw error;
    }
    setMe(identity);
    const signedIn = await fetchUser();
    // The account's own appearance is the theme from here on; the stored one was only
    // ever a stand-in for whoever was about to sign in.
    adoptAppearance(signedIn.appearance ?? "auto");
    setUser(signedIn);
    return identity;
  }, []);

  const refreshUser = useCallback(async () => {
    setUser(await fetchUser());
  }, []);

  // The theme toggle is in every shell and the account page sets the same value, so the
  // write-back belongs here rather than in either of them. A save that fails leaves the
  // choice applied on this device, which is what the user just asked for.
  useEffect(() => {
    if (!user) {
      setAppearanceWriter(null);
      return;
    }
    setAppearanceWriter((next) => {
      saveAppearance(next).catch(() => {
        toast.error("Your theme could not be saved to your account.");
      });
    });
    return () => {
      setAppearanceWriter(null);
    };
  }, [user]);

  const logout = useCallback(async () => {
    try {
      await directus.logout();
    } finally {
      await authStorage.set(null);
      setUser(null);
      setMe(null);
      setRefused(false);
      queryClient.clear();
    }
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, me, isAuthenticated: user !== null, isChecking, refused, login, logout, refreshUser }),
    [user, me, isChecking, refused, login, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isChecking, refused } = useAuth();
  const location = useLocation();

  if (isChecking) {
    return (
      <div className={styles.checking}>
        <Spinner size="lg" label="Checking your sign-in" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // Removed, suspended, or nobody this app serves: the sign-in page says the same
    // sentence for all three, because which one it was is not the caller's business.
    return (
      <Navigate
        to="/login"
        state={{ from: location, ...(refused ? { message: SIGNED_OUT } : {}) }}
        replace
      />
    );
  }

  return children;
}

/**
 * Keeps the three surfaces apart: anyone who asks for one that is not theirs is sent to
 * their own. `roleAdmits` is the rule — an admin is at home in the tutor app as well as
 * in `/admin`, and nobody else reaches either of the other two. Wrap it inside
 * `RequireAuth`, which is what guarantees there is a caller to have a role at all.
 */
export function RequireRole({ role, children }: { role: CallerRole; children: ReactNode }) {
  const { me } = useAuth();

  if (!roleAdmits(role, callerRole(me))) {
    return <Navigate to={homePath(me)} replace />;
  }

  return children;
}
