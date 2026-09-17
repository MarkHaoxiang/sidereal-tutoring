import { deleteItem, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { directus } from "@/lib/directus";
import type { FeedbackStatus } from "@/lib/schema";

export interface FeedbackListParams {
  studentId?: string;
  status?: FeedbackStatus[];
  limit?: number;
}

export const feedbackKeys = {
  all: ["feedback"] as const,
  list: (params: FeedbackListParams) => ["feedback", "list", params] as const,
  detail: (id: string) => ["feedback", "detail", id] as const,
  forHomework: (homeworkId: string) => ["feedback", "homework", homeworkId] as const,
};

function fetchFeedbackList(params: FeedbackListParams) {
  return directus.request(
    readItems("feedback", {
      fields: [
        "id",
        "status",
        "content",
        "date_created",
        { student: ["id", "name"] },
        // Feedback has no title; the homework it is about is what names it in a list.
        { homework: ["id", "title"] },
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

function fetchFeedback(id: string) {
  return directus.request(
    readItem("feedback", id, {
      fields: [
        "id",
        "status",
        "content",
        "generated_from",
        "date_created",
        { student: ["id", "name"] },
        { session: ["id", "scheduled_at"] },
        { homework: ["id", "title", "status", "due_on", "marking"] },
      ],
    })
  );
}

/** The feedback written about one piece of homework, newest first. */
function fetchFeedbackForHomework(homeworkId: string) {
  return directus.request(
    readItems("feedback", {
      fields: ["id", "status", "content", "date_created"],
      filter: { homework: { _eq: homeworkId } },
      sort: ["-date_created"],
      limit: -1,
    })
  );
}

export function useFeedbackForHomework(homeworkId: string | undefined) {
  return useQuery({
    queryKey: feedbackKeys.forHomework(homeworkId ?? ""),
    queryFn: () => fetchFeedbackForHomework(homeworkId ?? ""),
    enabled: Boolean(homeworkId),
  });
}

export type FeedbackListItem = Awaited<ReturnType<typeof fetchFeedbackList>>[number];
export type FeedbackDetail = Awaited<ReturnType<typeof fetchFeedback>>;

export interface FeedbackPatch {
  content?: string | null;
  status?: FeedbackStatus;
}

export function useFeedbackList(params: FeedbackListParams = {}) {
  return useQuery({
    queryKey: feedbackKeys.list(params),
    queryFn: () => fetchFeedbackList(params),
  });
}

export function useFeedback(id: string | undefined) {
  return useQuery({
    queryKey: feedbackKeys.detail(id ?? ""),
    queryFn: () => fetchFeedback(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useUpdateFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: FeedbackPatch }) =>
      directus.request(updateItem("feedback", id, patch, { fields: ["id", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: feedbackKeys.all });
    },
  });
}

export function useDeleteFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => directus.request(deleteItem("feedback", id)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: feedbackKeys.all });
    },
  });
}
