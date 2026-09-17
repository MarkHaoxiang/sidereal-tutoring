import { Link } from "react-router-dom";

import { GenerateSection } from "@/components/artefacts/GenerateSection";
import styles from "@/components/artefacts/artefacts.module.css";
import { SkeletonRows, StatusChip } from "@/components/ui";
import { formatDate, formatDateTime } from "@/lib/format";
import { useHomeworkList } from "@/lib/queries";

import { useStudentTab } from "./context";

export function HomeworkTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = useHomeworkList({ studentId });

  return (
    <div>
      {isLoading ? <SkeletonRows count={3} label="Loading homework" /> : null}
      {isError ? <p className={styles.status}>Could not load homework.</p> : null}

      {data ? (
        <GenerateSection
          studentId={studentId}
          kind="homework"
          empty={data.length === 0}
          emptyMessage="No homework yet."
        />
      ) : null}

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((item) => (
            <li key={item.id}>
              <Link to={`/students/${studentId}/homework/${item.id}`} className={styles.link}>
                <span className={styles.title}>{item.title ?? "Untitled homework"}</span>
                <StatusChip status={item.status} />
                <span className={styles.meta}>
                  <span>{formatDateTime(item.date_created)}</span>
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
