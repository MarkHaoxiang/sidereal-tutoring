import {
  keepPreviousData,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useMemo } from "react";

import { ApiError, api, unwrap } from "@/lib/api";
import type { paths } from "@/lib/api-schema";
import { assetBase64 } from "@/lib/files";
import { TypstError, figureAssets, readDiagnostics } from "@/lib/typeset";

import { homeworkKeys } from "./homework";

type RenderPost = paths["/api/typeset/render"]["post"];

/** A canonical document and the kind that says how to read it, as the contract has them. */
export type RenderBody = NonNullable<RenderPost["requestBody"]>["content"]["application/json"];
export type Rendered = RenderPost["responses"][200]["content"]["application/json"];

const NOTHING: Rendered = { pages: [], source: null };

export const typesetKeys = {
  render: (body: RenderBody | null) =>
    body === null
      ? (["typeset", "render", "nothing"] as const)
      : (["typeset", "render", body.kind, body.output ?? "svg", hashOf(body)] as const),
};

/** djb2 over the body's JSON: a cache key the length of a word, not of a paper. */
function hashOf(value: unknown): string {
  const json = JSON.stringify(value);
  let hash = 5381;
  for (let index = 0; index < json.length; index += 1) {
    hash = (hash * 33 + json.charCodeAt(index)) | 0;
  }
  return (hash >>> 0).toString(36);
}

async function previewTypst(source: string): Promise<string[]> {
  const result = await api.POST("/api/typeset/preview", { body: { source } });
  try {
    return unwrap(result).pages;
  } catch (error) {
    // A 422 carries the compiler's report beside the sentence; everything else does not.
    throw error instanceof ApiError ? new TypstError(error, readDiagnostics(result.error)) : error;
  }
}

async function renderTypst(body: RenderBody): Promise<Rendered> {
  const result = await api.POST("/api/typeset/render", { body });
  try {
    return unwrap(result);
  } catch (error) {
    throw error instanceof ApiError ? new TypstError(error, readDiagnostics(result.error)) : error;
  }
}

/** One SVG per page, for the tutor's live preview. A source that will not compile throws. */
export function usePreviewTypst() {
  return useMutation({ mutationFn: previewTypst });
}

/**
 * The body with the bytes every `figure` block in it names, or null while they are still
 * being fetched: an asset the request does not carry is a 422 before the compiler runs.
 */
export function useRenderAssets(body: RenderBody | null): RenderBody | null {
  const names = useMemo(() => (body === null ? [] : figureAssets(body)), [body]);
  const fetched = useQueries({
    queries: names.map((name) => ({
      queryKey: ["asset", name] as const,
      queryFn: () => assetBase64(name),
      staleTime: Infinity,
      retry: false,
    })),
  });

  if (body === null || names.length === 0) {
    return body;
  }
  const assets: Record<string, string> = {};
  names.forEach((name, index) => {
    const data = fetched[index]?.data;
    if (typeof data === "string") {
      assets[name] = data;
    }
  });
  // A figure whose file will not load is left out, so the render says so rather than hanging.
  const settled = fetched.every((result) => !result.isLoading);
  return settled ? { ...body, assets } : null;
}

/**
 * A canonical document as the typeset service sets it. The key is a hash of the body, so a
 * structure already rendered comes back from the cache and an edit asks for a new one; the
 * last good render stays on screen while the next one compiles.
 */
export function useRenderTypst(body: RenderBody | null) {
  return useQuery({
    queryKey: typesetKeys.render(body),
    queryFn: () => (body === null ? NOTHING : renderTypst(body)),
    enabled: body !== null,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    retry: false,
  });
}

/** Compiles the row's saved `content` again; the answer is the row, with `pdf` or `compile_error`. */
export function useCompileHomework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/homework/{homework_id}/compile", {
          params: { path: { homework_id: id } },
        })
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
    },
  });
}
