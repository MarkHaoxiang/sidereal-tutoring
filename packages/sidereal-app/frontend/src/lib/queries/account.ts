import { deleteFile, updateMe, uploadFiles } from "@directus/sdk";
import { useMutation } from "@tanstack/react-query";

import { ApiError, apiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { directus, directusUrl } from "@/lib/directus";
import type { Appearance } from "@/lib/theme";

// The signed-in user's own row. Every write here is `/users/me` with the caller's own
// token: the permission is `id = $CURRENT_USER` over these six fields and nothing else,
// so nobody reaches another account through this file.

const ID_ONLY = ["id"] as const;

export const WRONG_PASSWORD = "wrong_password";

export interface ProfileInput {
  first_name: string | null;
  last_name: string | null;
  email: string;
}

export interface PasswordChange {
  /** The address the account signs in with, which is what verifies the current password. */
  email: string;
  current: string;
  next: string;
}

export function saveAppearance(next: Appearance): Promise<unknown> {
  return directus.request(updateMe({ appearance: next }, { fields: [...ID_ONLY] }));
}

export function useSaveProfile() {
  const { refreshUser } = useAuth();
  return useMutation({
    mutationFn: (input: ProfileInput) => directus.request(updateMe(input, { fields: [...ID_ONLY] })),
    onSuccess: () => refreshUser(),
  });
}

export function useSaveAvatar() {
  const { user, refreshUser } = useAuth();
  const previous = user?.avatar ?? null;
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await directus.request(uploadFiles(form));
      await directus.request(updateMe({ avatar: uploaded.id }, { fields: [...ID_ONLY] }));
      await discard(previous);
    },
    onSuccess: () => refreshUser(),
  });
}

export function useRemoveAvatar() {
  const { user, refreshUser } = useAuth();
  const previous = user?.avatar ?? null;
  return useMutation({
    mutationFn: async () => {
      await directus.request(updateMe({ avatar: null }, { fields: [...ID_ONLY] }));
      await discard(previous);
    },
    onSuccess: () => refreshUser(),
  });
}

/**
 * The current password is checked by signing in with it on a request of its own, so a
 * wrong one costs nothing and the SDK's session is untouched either way.
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: async ({ email, current, next }: PasswordChange) => {
      await verify(email, current);
      await directus.request(updateMe({ password: next }, { fields: [...ID_ONLY] }));
    },
  });
}

// The old photo is the caller's own upload, so it goes with the new one. A refusal
// leaves a file behind, which is better than leaving the account wearing it.
async function discard(fileId: string | null) {
  if (!fileId) {
    return;
  }
  try {
    await directus.request(deleteFile(fileId));
  } catch {
    // Nothing to tell them: the avatar they asked about is already off the account.
  }
}

async function verify(email: string, password: string) {
  let response: Response;
  try {
    response = await fetch(`${directusUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, mode: "json" }),
    });
  } catch {
    throw new ApiError("We could not reach the server. Try again in a moment.", "unreachable", 0);
  }
  if (response.ok) {
    return;
  }
  if (response.status === 401) {
    throw new ApiError("That is not your current password.", WRONG_PASSWORD, 401);
  }
  const body: unknown = await response.json().catch(() => null);
  throw new ApiError(apiError(body), "verify_failed", response.status);
}
