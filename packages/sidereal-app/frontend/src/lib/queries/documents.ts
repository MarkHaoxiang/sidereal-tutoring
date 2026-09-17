import { deleteFile, deleteItem, readItem, readItems, uploadFiles } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createDocument, processDocument } from "@/lib/api";
import type { CreateDocumentBody } from "@/lib/api";
import { directus } from "@/lib/directus";
import type { DocumentStatus } from "@/lib/schema";

import { pollWhile } from "./poll";

export interface DocumentListParams {
  studentId?: string;
  status?: DocumentStatus[];
  limit?: number;
}

export interface LibraryListParams {
  status?: DocumentStatus[];
  limit?: number;
}

export const documentKeys = {
  all: ["documents"] as const,
  list: (params: DocumentListParams) => ["documents", "list", params] as const,
  library: (params: LibraryListParams) => ["documents", "library", params] as const,
  detail: (id: string) => ["documents", "detail", id] as const,
};

function fetchDocuments(params: DocumentListParams) {
  return directus.request(
    readItems("documents", {
      fields: [
        "id",
        "title",
        "kind",
        "status",
        "error",
        "source_url",
        "date_created",
        // A scan is several photos; the row says how many without reading them.
        "pages",
        { student: ["id", "name"] },
        { session: ["id", "scheduled_at"] },
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

// The agency library: everything filed against no student, which every tutor reads and
// only its author (or an admin) may change. `user_created` comes back null for a row a
// colleague added, because a tutor reads no other tutor's login.
function fetchLibraryDocuments(params: LibraryListParams) {
  return directus.request(
    readItems("documents", {
      fields: [
        "id",
        "title",
        "kind",
        "status",
        "error",
        "source_url",
        "date_created",
        "pages",
        { student: ["id", "name"] },
        { session: ["id", "scheduled_at"] },
        { user_created: ["id", "first_name", "last_name"] },
        { topics: ["id", "sort", { topic: ["id", "name"] }] },
      ],
      filter: {
        student: { _null: true },
        ...(params.status ? { status: { _in: params.status } } : {}),
      },
      sort: ["-date_created"],
      limit: params.limit ?? -1,
    })
  );
}

function fetchDocument(id: string) {
  return directus.request(
    readItem("documents", id, {
      fields: [
        "id",
        "title",
        "kind",
        "status",
        "error",
        "source_url",
        "text",
        "metadata",
        "date_created",
        "file",
        "transcription",
        { pages: ["id", "sort", "file"] },
        // A solutions scan is read against the paper's questions, so the page sets each
        // one above the answer to it.
        { paper: ["id", "title", "structure"] },
        { student: ["id", "name"] },
        { session: ["id", "scheduled_at"] },
        { user_created: ["id", "first_name", "last_name"] },
        { topics: ["id", "sort", { topic: ["id", "name"] }] },
      ],
    })
  );
}

export type DocumentListItem = Awaited<ReturnType<typeof fetchDocuments>>[number];
export type LibraryDocument = Awaited<ReturnType<typeof fetchLibraryDocuments>>[number];
export type DocumentDetail = Awaited<ReturnType<typeof fetchDocument>>;

const isUnsettled = (status: DocumentStatus) => status === "pending" || status === "processing";

export function useDocuments(params: DocumentListParams = {}) {
  return useQuery({
    queryKey: documentKeys.list(params),
    queryFn: () => fetchDocuments(params),
    // Processing happens in a FastAPI background task, so the list has to ask again.
    refetchInterval: pollWhile<DocumentListItem[]>((rows) => rows.some((row) => isUnsettled(row.status)), 2000),
  });
}

export function useLibraryDocuments(params: LibraryListParams = {}) {
  return useQuery({
    queryKey: documentKeys.library(params),
    queryFn: () => fetchLibraryDocuments(params),
    refetchInterval: pollWhile<LibraryDocument[]>((rows) => rows.some((row) => isUnsettled(row.status)), 2000),
  });
}

export function useDocument(id: string | undefined) {
  return useQuery({
    queryKey: documentKeys.detail(id ?? ""),
    queryFn: () => fetchDocument(id ?? ""),
    enabled: Boolean(id),
    refetchInterval: pollWhile<DocumentDetail>((row) => isUnsettled(row.status), 2000),
  });
}

/** Creates the row and starts ingestion; the row comes back as "pending". */
export function useCreateDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateDocumentBody) => createDocument(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

/** Re-runs ingestion for a pending or failed row. */
export function useRetryDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => processDocument(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

/** Puts a tutor's file in Directus and answers with its id, ready for a `file` source. */
export function useUploadMaterialFile() {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await directus.request(uploadFiles(form));
      return uploaded.id;
    },
  });
}

/**
 * A scan's pages, uploaded in the order the tutor chose them: the ids come back in that
 * order, which is the order the transcriber reads them in.
 */
export function useUploadScanPages() {
  return useMutation({
    mutationFn: async (files: File[]) => {
      const ids: string[] = [];
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        const uploaded = await directus.request(uploadFiles(form));
        ids.push(uploaded.id);
      }
      return ids;
    },
  });
}

/** Deletes the row and, when the material was an upload, the file behind it. */
export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, fileId }: { id: string; fileId?: string | null }) => {
      await directus.request(deleteItem("documents", id));
      if (fileId) {
        await directus.request(deleteFile(fileId));
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}
