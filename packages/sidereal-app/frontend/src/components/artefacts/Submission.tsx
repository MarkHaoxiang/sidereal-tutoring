import { FileLink, Markdown } from "@/components/ui";
import { cx } from "@/lib/cx";
import { formatDateTime } from "@/lib/format";

import styles from "./artefacts.module.css";

export interface SubmissionProps {
  submittedAt: string | null;
  submission: string | null;
  /** The id of a photo or PDF of the student's working, when they attached one. */
  attachmentId?: string | null;
}

/** What the student handed in, above the homework itself — the first thing to read. */
export function Submission({ submittedAt, submission, attachmentId = null }: SubmissionProps) {
  if (!submittedAt && !submission && !attachmentId) {
    return null;
  }
  return (
    <section className={cx(styles.section, styles.handedIn)}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Handed in</h2>
        {submittedAt ? <span className={styles.status}>{formatDateTime(submittedAt)}</span> : null}
      </div>
      {submission ? (
        <Markdown>{submission}</Markdown>
      ) : (
        <p className={styles.status}>Handed in without writing anything.</p>
      )}
      {attachmentId ? (
        <p className={styles.attachment}>
          <FileLink fileId={attachmentId} fallbackName="the student's working" />
        </p>
      ) : null}
    </section>
  );
}
