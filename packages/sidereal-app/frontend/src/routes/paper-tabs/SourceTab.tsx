import { PaperSource } from "@/components/papers/PaperSource";
import { buildPatch } from "@/components/papers/draft";
import styles from "@/components/papers/papers.module.css";

import { usePaperTab } from "./context";

export function SourceTab() {
  const { draft } = usePaperTab();
  const built = buildPatch(draft);

  if (!built.ok) {
    return (
      <>
        <p className={styles.note}>
          The file is generated from the structure every time, and there is something in the
          structure that cannot be set yet.
        </p>
        <ul className={styles.problems}>
          {built.problems.map((problem) => (
            <li key={problem} className={styles.problem}>
              {problem}
            </li>
          ))}
        </ul>
      </>
    );
  }

  return <PaperSource structure={built.patch.structure} fileName={draft.title || "paper"} />;
}
