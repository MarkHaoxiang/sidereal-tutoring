import { deleteItem, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { directus } from "@/lib/directus";
import type { PlanStatus } from "@/lib/schema";

export interface PlanListParams {
  studentId?: string;
  status?: PlanStatus[];
  limit?: number;
}

export const planKeys = {
  all: ["plans"] as const,
  list: (params: PlanListParams) => ["plans", "list", params] as const,
  detail: (id: string) => ["plans", "detail", id] as const,
};

function fetchPlans(params: PlanListParams) {
  return directus.request(
    readItems("plans", {
      fields: [
        "id",
        "title",
        "status",
        "period_start",
        "period_end",
        "date_created",
        { student: ["id", "name"] },
      ],
      filter: {
        ...(params.studentId ? { student: { _eq: params.studentId } } : {}),
        ...(params.status ? { status: { _in: params.status } } : {}),
      },
      sort: ["-date_created"],
      limit: params.limit ?? -1,
    })
  );
}

function fetchPlan(id: string) {
  return directus.request(
    readItem("plans", id, {
      fields: [
        "id",
        "title",
        "content",
        "status",
        "period_start",
        "period_end",
        "generated_from",
        "date_created",
        { student: ["id", "name"] },
      ],
    })
  );
}

export type PlanListItem = Awaited<ReturnType<typeof fetchPlans>>[number];
export type PlanDetail = Awaited<ReturnType<typeof fetchPlan>>;

export interface PlanPatch {
  title?: string | null;
  content?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  status?: PlanStatus;
}

export function usePlans(params: PlanListParams = {}) {
  return useQuery({
    queryKey: planKeys.list(params),
    queryFn: () => fetchPlans(params),
  });
}

export function usePlan(id: string | undefined) {
  return useQuery({
    queryKey: planKeys.detail(id ?? ""),
    queryFn: () => fetchPlan(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useUpdatePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: PlanPatch }) =>
      directus.request(updateItem("plans", id, patch, { fields: ["id", "title", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: planKeys.all });
    },
  });
}

export function useDeletePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => directus.request(deleteItem("plans", id)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: planKeys.all });
    },
  });
}
