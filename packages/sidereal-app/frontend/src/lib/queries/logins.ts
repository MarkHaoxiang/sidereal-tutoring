import { readUser } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, apiError, unwrap } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { directus } from "@/lib/directus";

import { studentKeys } from "./students";

export const loginKeys = {
  all: ["logins"] as const,
  detail: (userId: string) => ["logins", userId] as const,
};

/**
 * The address a linked login signs in with. `students.user` is a `directus_users` id,
 * which is not a collection of this app's schema, so it takes a request of its own.
 */
export function useStudentLogin(userId: string | null) {
  return useQuery({
    queryKey: loginKeys.detail(userId ?? ""),
    queryFn: () => directus.request(readUser(userId ?? "", { fields: ["id", "email"] })),
    enabled: Boolean(userId),
  });
}

/** The login the app answers with once it has made one. */
export type StudentLogin = components["schemas"]["StudentLogin"];

export interface CreateLoginInput {
  studentId: string;
  email: string;
  password: string;
}

export interface ResetPasswordInput {
  studentId: string;
  password: string;
}

function detailCode(error: unknown): string | undefined {
  const code = (error as { detail?: { code?: unknown } } | null | undefined)?.detail?.code;
  return typeof code === "string" ? code : undefined;
}

/** A 204 carries no body, which `unwrap` would read as a failure; the status decides. */
function expectNoContent(result: { error?: unknown; response: Response }): void {
  if (!result.response.ok) {
    throw new ApiError(apiError(result.error), detailCode(result.error), result.response.status);
  }
}

export function useCreateStudentLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ studentId, email, password }: CreateLoginInput) =>
      unwrap(
        await api.POST("/api/students/{student_id}/login", {
          params: { path: { student_id: studentId } },
          body: { email, password },
        })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}

export function useResetStudentPassword() {
  return useMutation({
    mutationFn: async ({ studentId, password }: ResetPasswordInput) => {
      expectNoContent(
        await api.POST("/api/students/{student_id}/login/password", {
          params: { path: { student_id: studentId } },
          body: { password },
        })
      );
    },
  });
}

/** Only the login goes: the student's sessions, homework and feedback all stay. */
export function useRemoveStudentLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (studentId: string) => {
      expectNoContent(
        await api.DELETE("/api/students/{student_id}/login", {
          params: { path: { student_id: studentId } },
        })
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}
