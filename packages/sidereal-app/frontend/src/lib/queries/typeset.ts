import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, unwrap } from "@/lib/api";
import { TypstError, readDiagnostics } from "@/lib/typeset";

import { homeworkKeys } from "./homework";

async function previewTypst(source: string): Promise<string[]> {
  const result = await api.POST("/api/typeset/preview", { body: { source } });
  try {
    return unwrap(result).pages;
  } catch (error) {
    // A 422 carries the compiler's report beside the sentence; everything else does not.
    throw error instanceof ApiError ? new TypstError(error, readDiagnostics(result.error)) : error;
  }
}

/** One SVG per page, for the tutor's live preview. A source that will not compile throws. */
export function usePreviewTypst() {
  return useMutation({ mutationFn: previewTypst });
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
