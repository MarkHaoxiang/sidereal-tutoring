import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, unwrap } from "@/lib/api";
import type { paths } from "@/lib/api-schema";
import { TypstError, readDiagnostics } from "@/lib/typeset";

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
