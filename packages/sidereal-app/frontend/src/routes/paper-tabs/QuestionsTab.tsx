import { PaperDetails } from "@/components/papers/PaperDetails";
import { QuestionsEditor } from "@/components/papers/QuestionsEditor";
import styles from "@/components/papers/papers.module.css";

import { usePaperTab } from "./context";

export function QuestionsTab() {
  const { draft, edit } = usePaperTab();

  return (
    <div className={styles.stack}>
      <QuestionsEditor
        questions={draft.questions}
        onChange={(questions) => {
          edit({ questions });
        }}
      />
      <PaperDetails draft={draft} onChange={edit} />
    </div>
  );
}
