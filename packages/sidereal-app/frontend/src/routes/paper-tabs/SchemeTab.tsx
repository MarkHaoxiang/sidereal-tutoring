import { MarkSchemeEditor } from "@/components/papers/MarkSchemeEditor";
import { allQuestions } from "@/components/papers/draft";

import { usePaperTab } from "./context";

export function SchemeTab() {
  const { draft, edit } = usePaperTab();

  return (
    <MarkSchemeEditor
      scheme={draft.scheme}
      questions={allQuestions(draft)}
      passages={draft.passages}
      onChange={(scheme) => {
        edit({ scheme });
      }}
    />
  );
}
