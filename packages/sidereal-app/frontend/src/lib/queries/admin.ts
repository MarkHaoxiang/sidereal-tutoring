import { readRoles, readUsers, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, expectNoContent, unwrap } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { directus } from "@/lib/directus";

import { pollWhile } from "./poll";
import { studentKeys } from "./students";

export type AdminHealth = components["schemas"]["AdminHealth"];
export type TutorAccount = components["schemas"]["TutorAccount"];
export type TutorStatus = components["schemas"]["TutorStatus"];
export type AdminJob = components["schemas"]["AdminJob"];
export type AdminJobStatus = components["schemas"]["JobStatus"];

export interface AdminJobParams {
  status?: AdminJobStatus;
  limit?: number;
}

export const adminKeys = {
  all: ["admin"] as const,
  health: ["admin", "health"] as const,
  tutors: ["admin", "tutors"] as const,
  tutorUsers: ["admin", "tutor-users"] as const,
  jobs: (params: AdminJobParams) => ["admin", "jobs", params] as const,
};

const HEALTH_INTERVAL = 30_000;
const JOBS_INTERVAL = 3000;

export function useAdminHealth() {
  return useQuery({
    queryKey: adminKeys.health,
    queryFn: async () => unwrap(await api.GET("/api/admin/health")),
    refetchInterval: HEALTH_INTERVAL,
  });
}

/** Admin only, so the tutor app passes `false` unless the caller is one. */
export function useTutors(enabled = true) {
  return useQuery({
    queryKey: adminKeys.tutors,
    queryFn: async () => unwrap(await api.GET("/api/admin/tutors")),
    enabled,
  });
}

export interface TutorInput {
  email: string;
  password: string;
  first_name?: string | null;
  last_name?: string | null;
}

export function useCreateTutor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: TutorInput) => unwrap(await api.POST("/api/admin/tutors", { body })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function useResetTutorPassword() {
  return useMutation({
    mutationFn: async ({ userId, password }: { userId: string; password: string }) => {
      expectNoContent(
        await api.POST("/api/admin/tutors/{user_id}/password", {
          params: { path: { user_id: userId } },
          body: { password },
        })
      );
    },
  });
}

export function useSetTutorStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, status }: { userId: string; status: TutorStatus }) =>
      unwrap(
        await api.PATCH("/api/admin/tutors/{user_id}", {
          params: { path: { user_id: userId } },
          body: { status },
        })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

/** Refused with a 409 while the tutor still has students; the message says to reassign them. */
export function useRemoveTutor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (userId: string) => {
      expectNoContent(
        await api.DELETE("/api/admin/tutors/{user_id}", { params: { path: { user_id: userId } } })
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function useAdminJobs(params: AdminJobParams = {}) {
  return useQuery({
    queryKey: adminKeys.jobs(params),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/admin/jobs", {
          params: { query: { ...(params.status ? { status: params.status } : {}), ...(params.limit ? { limit: params.limit } : {}) } },
        })
      ),
    refetchInterval: pollWhile<AdminJob[]>(
      (jobs) => jobs.some((row) => row.job.status === "queued" || row.job.status === "running"),
      JOBS_INTERVAL
    ),
  });
}

// The role is found by name, then the users by its id: the SDK's filter types stop at the
// relation, so a single nested `role.name` filter is not expressible here.
const TUTOR_ROLE = "Tutor";

async function fetchTutorUsers() {
  const roles = await directus.request(
    readRoles({ fields: ["id"], filter: { name: { _eq: TUTOR_ROLE } }, limit: 1 })
  );
  const role = roles[0];
  if (!role) {
    return [];
  }
  return directus.request(
    readUsers({
      fields: ["id", "email", "first_name", "last_name"],
      filter: { role: { _eq: role.id } },
      sort: ["email"],
      limit: -1,
    })
  );
}

export type TutorUser = Awaited<ReturnType<typeof fetchTutorUsers>>[number];

/**
 * The Tutor-role users a student can be handed to. Only an admin reads `directus_roles`
 * widely enough for this filter, so it is asked for only where one is signed in.
 */
export function useTutorUsers(enabled = true) {
  return useQuery({ queryKey: adminKeys.tutorUsers, queryFn: fetchTutorUsers, enabled });
}

/** Hands a student to another tutor, or to nobody. Admin only: a tutor cannot write `tutor`. */
export function useReassignStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, tutor }: { id: string; tutor: string | null }) =>
      directus.request(updateItem("students", id, { tutor }, { fields: ["id"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
      void queryClient.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function tutorName(tutor: { first_name?: string | null; last_name?: string | null; email?: string | null }): string {
  const name = [tutor.first_name, tutor.last_name].filter(Boolean).join(" ").trim();
  return name || tutor.email || "Unnamed tutor";
}

// The address `scripts/directus-bootstrap.sh` gives the account the agent surface signs in as.
// It holds the Tutor role and so comes back with the tutors, but it is not a person.
const SERVICE_ACCOUNT = "agent@sidereal.example.com";

export function isServiceAccount(tutor: { email?: string | null }): boolean {
  return (tutor.email ?? "").toLowerCase() === SERVICE_ACCOUNT;
}
