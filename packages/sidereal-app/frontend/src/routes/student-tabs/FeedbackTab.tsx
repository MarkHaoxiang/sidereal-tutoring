import { Link } from "react-router-dom";

import { GenerateSection } from "@/components/artefacts/GenerateSection";
import styles from "@/components/artefacts/artefacts.module.css";
import { Spinner, StatusChip } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { useFeedbackList } from "@/lib/queries";

import { useStudentTab } from "./context";

/** Feedback has no title, so its first written line names the row. */
function firstLine(content: string | null): string {
  const line = (content ?? "")
    .split("\n")
    .map((part) => part.replace(/^#+\s*/, "").trim())
    .find((part) => part.length > 0);
  return line ?? "Untitled feedback";
}

export function FeedbackTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = useFeedbackList({ studentId });

  return (
    <div>
      {isLoading ? (
        <p className={styles.status}>
          <Spinner /> Loading feedback…
        </p>
      ) : null}
      {isError ? <p className={styles.status}>Could not load feedback.</p> : null}

      {data ? (
        <GenerateSection
          studentId={studentId}
          kind="feedback"
          empty={data.length === 0}
          emptyMessage="No feedback yet. Generate a note from this student's material."
        />
      ) : null}

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((item) => (
            <li key={item.id}>
              <Link to={`/students/${studentId}/feedback/${item.id}`} className={styles.link}>
                <span className={styles.top}>
                  <span className={styles.title}>{firstLine(item.content)}</span>
                  <StatusChip status={item.status} />
                </span>
                <span className={styles.meta}>Created {formatDateTime(item.date_created)}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
