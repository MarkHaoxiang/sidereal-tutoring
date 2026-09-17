import { Link } from "react-router-dom";

import { GenerateSection } from "@/components/artefacts/GenerateSection";
import { JobsPanel } from "@/components/artefacts/JobsPanel";
import styles from "@/components/artefacts/artefacts.module.css";
import { SkeletonRows, StatusChip } from "@/components/ui";
import { feedbackTitle } from "@/lib/feedback";
import { formatDateTime } from "@/lib/format";
import { useFeedbackList } from "@/lib/queries";

import { useStudentTab } from "./context";

export function FeedbackTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = useFeedbackList({ studentId });

  return (
    <div>
      {isLoading ? <SkeletonRows count={3} label="Loading feedback" /> : null}
      {isError ? <p className={styles.status}>Could not load feedback.</p> : null}

      {data ? (
        <GenerateSection
          studentId={studentId}
          kind="feedback"
          empty={data.length === 0}
          emptyMessage="No feedback yet."
        />
      ) : null}

      <JobsPanel studentId={studentId} kind="feedback" />

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((item) => (
            <li key={item.id}>
              <Link to={`/students/${studentId}/feedback/${item.id}`} className={styles.link}>
                <span className={styles.title}>{feedbackTitle(item)}</span>
                <StatusChip status={item.status} />
                <span className={styles.meta}>{formatDateTime(item.date_created)}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
