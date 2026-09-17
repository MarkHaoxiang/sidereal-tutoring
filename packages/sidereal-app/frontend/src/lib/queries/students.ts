import { createItem, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, expectNoContent, unwrap } from "@/lib/api";
import { directus } from "@/lib/directus";
import type { StudentStatus } from "@/lib/schema";

export interface StudentListParams {
  status?: StudentStatus;
}

export const studentKeys = {
  all: ["students"] as const,
  list: (params: StudentListParams) => ["students", "list", params] as const,
  detail: (id: string) => ["students", "detail", id] as const,
};

function fetchStudents(params: StudentListParams) {
  return directus.request(
    readItems("students", {
      fields: ["id", "name", "level", "subjects", "notes", "status", "tutor", "date_created"],
      filter: params.status ? { status: { _eq: params.status } } : {},
      sort: ["name"],
      limit: -1,
    })
  );
}

function fetchStudent(id: string) {
  return directus.request(
    readItem("students", id, {
      fields: [
        "id",
        "name",
        "level",
        "subjects",
        "notes",
        "status",
        // Whose student this is. Only an admin can change it, from the student page header.
        "tutor",
        "date_created",
        "date_updated",
        // The id of the student's login, if they have one; `useStudentLogin` reads its email.
        "user",
      ],
    })
  );
}

export type StudentListItem = Awaited<ReturnType<typeof fetchStudents>>[number];
export type StudentDetail = Awaited<ReturnType<typeof fetchStudent>>;

export interface StudentInput {
  name: string;
  level?: string | null;
  subjects?: string[];
  notes?: string | null;
  status?: StudentStatus;
}

export function useStudents(params: StudentListParams = {}) {
  return useQuery({
    queryKey: studentKeys.list(params),
    queryFn: () => fetchStudents(params),
  });
}

export function useStudent(id: string | undefined) {
  return useQuery({
    queryKey: studentKeys.detail(id ?? ""),
    queryFn: () => fetchStudent(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useCreateStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: StudentInput) =>
      directus.request(createItem("students", input, { fields: ["id", "name", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}

export function useUpdateStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<StudentInput> }) =>
      directus.request(updateItem("students", id, patch, { fields: ["id", "name", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}

/** Archiving takes the student's sign-in away with them; unarchiving gives it back. */
export function useArchiveStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/students/{student_id}/archive", { params: { path: { student_id: id } } })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}

export function useUnarchiveStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/students/{student_id}/unarchive", { params: { path: { student_id: id } } })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}

/**
 * The student, their sign-in, their files and everything filed against them. Material they
 * were given stays, with no student on it: it becomes library material.
 */
export function useDeleteStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      expectNoContent(
        await api.DELETE("/api/students/{student_id}", { params: { path: { student_id: id } } })
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}
