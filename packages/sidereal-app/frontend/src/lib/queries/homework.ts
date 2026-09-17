import { deleteItem, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api";
import { directus } from "@/lib/directus";
import type { HomeworkStatus, Marking } from "@/lib/schema";

import { meKeys } from "./me";

export interface HomeworkListParams {
  studentId?: string;
  status?: HomeworkStatus[];
  limit?: number;
}

export const homeworkKeys = {
  all: ["homework"] as const,
  list: (params: HomeworkListParams) => ["homework", "list", params] as const,
  detail: (id: string) => ["homework", "detail", id] as const,
  questions: (ids: string[]) => ["homework", "questions", ids] as const,
};

function fetchHomeworkList(params: HomeworkListParams) {
  return directus.request(
    readItems("homework", {
      fields: ["id", "title", "status", "due_on", "date_created", { student: ["id", "name"] }],
      filter: {
        ...(params.studentId ? { student: { _eq: params.studentId } } : {}),
        ...(params.status ? { status: { _in: params.status } } : {}),
      },
      sort: ["-date_created"],
      limit: params.limit ?? -1,
    })
  );
}

function fetchHomework(id: string) {
  return directus.request(
    readItem("homework", id, {
      fields: [
        "id",
        "title",
        "content",
        "format",
        "compile_error",
        "status",
        "due_on",
        "submission",
        "submission_transcription",
        "submitted_at",
        "marking",
        "generated_from",
        "date_created",
        "pdf",
        "submission_file",
        { student: ["id", "name"] },
        { session: ["id", "scheduled_at"] },
        {
          questions: [
            "id",
            "sort",
            {
              question: [
                "id",
                "text",
                "answer",
                "number",
                "marks",
                { topics: ["id", "sort", { topic: ["id", "name"] }] },
              ],
            },
          ],
        },
        { topics: ["id", "sort", { topic: ["id", "name"] }] },
      ],
    })
  );
}

function fetchQuestions(ids: string[]) {
  return directus.request(
    readItems("questions", {
      fields: ["id", "text", "answer", "topic", "difficulty", { topics: ["id", "sort", { topic: ["id", "name"] }] }],
      filter: { id: { _in: ids } },
      limit: -1,
    })
  );
}

export type HomeworkListItem = Awaited<ReturnType<typeof fetchHomeworkList>>[number];
export type HomeworkDetail = Awaited<ReturnType<typeof fetchHomework>>;

export interface HomeworkPatch {
  title?: string | null;
  content?: string | null;
  due_on?: string | null;
  status?: HomeworkStatus;
  marking?: Marking | null;
}

export function useHomeworkList(params: HomeworkListParams = {}, enabled = true) {
  return useQuery({
    queryKey: homeworkKeys.list(params),
    queryFn: () => fetchHomeworkList(params),
    enabled,
  });
}

export function useHomework(id: string | undefined) {
  return useQuery({
    queryKey: homeworkKeys.detail(id ?? ""),
    queryFn: () => fetchHomework(id ?? ""),
    enabled: Boolean(id),
  });
}

/** The questions a generation wrote, which its `generated_from` records by id. */
export function useGeneratedQuestions(ids: string[]) {
  return useQuery({
    queryKey: homeworkKeys.questions(ids),
    queryFn: () => fetchQuestions(ids),
    enabled: ids.length > 0,
  });
}

export function useUpdateHomework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: HomeworkPatch }) =>
      directus.request(updateItem("homework", id, patch, { fields: ["id", "title", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
    },
  });
}

/** The marks and the status in one write, so finishing marking is a single step. */
export function useSaveMarking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, marking, status }: { id: string; marking: Marking; status?: HomeworkStatus }) =>
      directus.request(
        updateItem(
          "homework",
          id,
          { marking, ...(status ? { status } : {}) },
          { fields: ["id", "status"] }
        )
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
      void queryClient.invalidateQueries({ queryKey: meKeys.all });
    },
  });
}

/**
 * Reads the handed-in photo or PDF into `submission_transcription`. The call transcribes
 * before it answers, and its answer is the row.
 */
export function useTranscribeSubmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/homework/{homework_id}/transcribe", {
          params: { path: { homework_id: id } },
        })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
      void queryClient.invalidateQueries({ queryKey: meKeys.all });
    },
  });
}

export function useDeleteHomework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => directus.request(deleteItem("homework", id)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
    },
  });
}
