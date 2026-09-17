import { MarkSchemeEditor } from "@/components/papers/MarkSchemeEditor";
import { allQuestions } from "@/components/papers/draft";
import { Button } from "@/components/ui";

import { usePaperTab } from "./context";

export function SchemeTab() {
  const { draft, edit, extractScheme } = usePaperTab();

  return (
    <MarkSchemeEditor
      scheme={draft.scheme}
      questions={allQuestions(draft)}
      passages={draft.passages}
      onChange={(scheme) => {
        edit({ scheme });
      }}
      emptyAction={<Button onClick={extractScheme}>Extract mark scheme</Button>}
    />
  );
}
