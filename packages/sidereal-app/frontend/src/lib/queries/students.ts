import { createItem, deleteItem, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
      fields: ["id", "name", "level", "subjects", "notes", "status", "date_created"],
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

export function useDeleteStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => directus.request(deleteItem("students", id)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: studentKeys.all });
    },
  });
}
