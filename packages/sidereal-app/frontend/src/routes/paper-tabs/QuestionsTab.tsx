import { PaperDetails } from "@/components/papers/PaperDetails";
import { PassagesEditor } from "@/components/papers/PassagesEditor";
import { QuestionsEditor } from "@/components/papers/QuestionsEditor";
import { SectionsEditor } from "@/components/papers/SectionsEditor";
import { emptySection } from "@/components/papers/draft";
import styles from "@/components/papers/papers.module.css";
import { Button } from "@/components/ui";

import { usePaperTab } from "./context";

export function QuestionsTab() {
  const { draft, edit } = usePaperTab();
  const grouped = draft.sections.length > 0;

  return (
    <div className={styles.stack}>
      {grouped && draft.questions.length === 0 ? null : (
        <QuestionsEditor
          questions={draft.questions}
          passages={draft.passages}
          onChange={(questions) => {
            edit({ questions });
          }}
        />
      )}

      {grouped ? (
        <SectionsEditor
          sections={draft.sections}
          passages={draft.passages}
          onChange={(sections) => {
            edit({ sections });
          }}
          onUngroup={(index) => {
            const section = draft.sections[index];
            edit({
              questions: [...draft.questions, ...(section?.questions ?? [])],
              sections: draft.sections.filter((_, position) => position !== index),
            });
          }}
        />
      ) : (
        <div className={styles.addRow}>
          <Button
            onClick={() => {
              edit({
                questions: [],
                sections: [{ ...emptySection(), title: "Section A", questions: draft.questions }],
              });
            }}
          >
            Group into a section
          </Button>
        </div>
      )}

      <PassagesEditor
        passages={draft.passages}
        onChange={(passages) => {
          edit({ passages });
        }}
      />
      <PaperDetails draft={draft} onChange={edit} />
    </div>
  );
}
