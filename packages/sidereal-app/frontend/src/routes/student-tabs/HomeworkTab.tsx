import { Link } from "react-router-dom";

import { GenerateSection } from "@/components/artefacts/GenerateSection";
import styles from "@/components/artefacts/artefacts.module.css";
import { Spinner, StatusChip } from "@/components/ui";
import { formatDate, formatDateTime } from "@/lib/format";
import { useHomeworkList } from "@/lib/queries";

import { useStudentTab } from "./context";

export function HomeworkTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = useHomeworkList({ studentId });

  return (
    <div>
      {isLoading ? (
        <p className={styles.status}>
          <Spinner /> Loading homework…
        </p>
      ) : null}
      {isError ? <p className={styles.status}>Could not load homework.</p> : null}

      {data ? (
        <GenerateSection
          studentId={studentId}
          kind="homework"
          empty={data.length === 0}
          emptyMessage="No homework yet. Generate a set from this student's material."
        />
      ) : null}

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((item) => (
            <li key={item.id}>
              <Link to={`/students/${studentId}/homework/${item.id}`} className={styles.link}>
                <span className={styles.top}>
                  <span className={styles.title}>{item.title ?? "Untitled homework"}</span>
                  <StatusChip status={item.status} />
                </span>
                <span className={styles.meta}>
                  <span>Created {formatDateTime(item.date_created)}</span>
                  {item.due_on ? <span>Due {formatDate(item.due_on)}</span> : null}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
