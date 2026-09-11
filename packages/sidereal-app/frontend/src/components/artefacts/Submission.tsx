import { Markdown } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

import styles from "./artefacts.module.css";

export interface SubmissionProps {
  submittedAt: string | null;
  submission: string | null;
}

/** What the student handed in, above the homework itself — the first thing to read. */
export function Submission({ submittedAt, submission }: SubmissionProps) {
  if (!submittedAt && !submission) {
    return null;
  }
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Handed in</h2>
        {submittedAt ? <span className={styles.status}>{formatDateTime(submittedAt)}</span> : null}
      </div>
      {submission ? (
        <Markdown>{submission}</Markdown>
      ) : (
        <p className={styles.status}>Handed in without writing anything.</p>
      )}
    </section>
  );
}
