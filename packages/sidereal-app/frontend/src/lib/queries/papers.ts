import { deleteItem, deleteItems, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api";
import { directus } from "@/lib/directus";
import type { CanonicalMarkScheme, CanonicalPaper, PaperStatus } from "@/lib/schema";

export const paperKeys = {
  all: ["papers"] as const,
  list: () => ["papers", "list"] as const,
  detail: (id: string) => ["papers", "detail", id] as const,
};

function fetchPapers() {
  return directus.request(
    readItems("papers", {
      fields: [
        "id",
        "title",
        "board",
        "year",
        "total_marks",
        "status",
        "date_created",
        // The list shows how many questions a paper holds, and the structure is where
        // that lives: `papers` has no o2m alias onto `questions`.
        "structure",
        { user_created: ["id", "first_name", "last_name"] },
      ],
      sort: ["-date_created"],
      limit: -1,
    })
  );
}

function fetchPaper(id: string) {
  return directus.request(
    readItem("papers", id, {
      fields: [
        "id",
        "title",
        "source",
        "board",
        "year",
        "time_minutes",
        "total_marks",
        "instructions",
        "status",
        "structure",
        "mark_scheme",
        "rendered_pdf",
        "mark_scheme_pdf",
        "generated_from",
        "date_created",
        // The draft reloads when this moves, and not while a tutor is still typing.
        "date_updated",
        { document: ["id", "title"] },
        { user_created: ["id", "first_name", "last_name"] },
      ],
    })
  );
}

export type PaperListItem = Awaited<ReturnType<typeof fetchPapers>>[number];
export type PaperDetail = Awaited<ReturnType<typeof fetchPaper>>;

/** What Save writes: the whole structure, the whole mark scheme, and the columns beside them. */
export interface PaperPatch {
  title: string;
  source: string | null;
  board: string | null;
  year: number | null;
  time_minutes: number | null;
  total_marks: number | null;
  instructions: string | null;
  structure: CanonicalPaper;
  mark_scheme: CanonicalMarkScheme | null;
}

export interface WorksheetInput {
  paperId: string;
  question_numbers: string[];
  student_id?: string | null;
  title?: string | null;
  due?: string | null;
}

export interface ExtractMarkSchemeInput {
  paperId: string;
  document_id: string;
}

export function usePapers() {
  return useQuery({ queryKey: paperKeys.list(), queryFn: fetchPapers });
}

export function usePaper(id: string | undefined) {
  return useQuery({
    queryKey: paperKeys.detail(id ?? ""),
    queryFn: () => fetchPaper(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useSavePaper() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: PaperPatch }) =>
      directus.request(updateItem("papers", id, patch)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.all });
    },
  });
}

export function useSetPaperStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: PaperStatus }) =>
      directus.request(updateItem("papers", id, { status })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.all });
    },
  });
}

/** Renders the stored structure again; the PDFs on the row follow it. */
export function useRenderPaper() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.POST("/api/papers/{paper_id}/render", { params: { path: { paper_id: id } } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.all });
    },
  });
}

/** Some of a paper's questions as a PDF. Nothing is filed against the student. */
export function useWorksheet() {
  return useMutation({
    mutationFn: async ({ paperId, ...body }: WorksheetInput) =>
      unwrap(
        await api.POST("/api/papers/{paper_id}/worksheet", {
          params: { path: { paper_id: paperId } },
          body,
        })
      ),
  });
}

/** Reads a mark scheme document against the paper's stored structure. The paper itself,
 * its questions and its rendered PDF are left as they are. */
export function useExtractMarkScheme() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ paperId, document_id }: ExtractMarkSchemeInput) =>
      unwrap(
        await api.POST("/api/papers/{paper_id}/extract_mark_scheme", {
          params: { path: { paper_id: paperId } },
          body: { document_id },
        })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.all });
    },
  });
}

/**
 * The paper and the `questions` rows lifted from it. `questions.paper` is `SET NULL`, so
 * deleting only the paper would leave those rows behind with nothing pointing at them.
 */
export function useDeletePaper() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const rows = await directus.request(
        readItems("questions", { fields: ["id"], filter: { paper: { _eq: id } }, limit: -1 })
      );
      if (rows.length > 0) {
        await directus.request(
          deleteItems(
            "questions",
            rows.map((row) => row.id)
          )
        );
      }
      await directus.request(deleteItem("papers", id));
    },
    // The list only: invalidating the detail would refetch the row that has just gone.
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: paperKeys.list() });
    },
  });
}
