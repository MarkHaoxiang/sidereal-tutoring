import { Link } from "react-router-dom";

import { feedbackTitle } from "@/components/student/feedback";
import studentStyles from "@/components/student/student.module.css";
import { EmptyState, Spinner } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { useMyFeedbackList } from "@/lib/queries";

import styles from "./me.module.css";

export function StudentFeedbackListPage() {
  const { data, isLoading, isError } = useMyFeedbackList();

  const rows = data ?? [];

  return (
    <div className={styles.stack}>
      <h1 className={styles.heading}>Feedback</h1>

      {isLoading ? (
        <p className={styles.loading}>
          <Spinner /> Loading your feedback…
        </p>
      ) : null}
      {isError ? <p className={styles.status}>Your feedback could not be loaded. Try again in a moment.</p> : null}

      {rows.length > 0 ? (
        <ul className={styles.list}>
          {rows.map((row) => (
            <li key={row.id}>
              <Link to={`/me/feedback/${row.id}`} className={studentStyles.row}>
                <span className={studentStyles.rowTitle}>{feedbackTitle(row.content)}</span>
                <span className={studentStyles.rowMeta}>{formatDate(row.date_created)}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <EmptyState message="No feedback yet. It turns up here after a lesson." />
      ) : null}
    </div>
  );
}
