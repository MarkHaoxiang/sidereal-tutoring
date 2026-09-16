import { MarkSchemeEditor } from "@/components/papers/MarkSchemeEditor";

import { usePaperTab } from "./context";

export function SchemeTab() {
  const { draft, edit } = usePaperTab();

  return (
    <MarkSchemeEditor
      scheme={draft.scheme}
      questions={draft.questions}
      onChange={(scheme) => {
        edit({ scheme });
      }}
    />
  );
}
