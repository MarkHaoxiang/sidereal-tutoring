import { Link } from "react-router-dom";

import { StatusChip } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { MyHomeworkListItem } from "@/lib/queries";

import { dueLabel, isOverdue } from "./homework";
import styles from "./student.module.css";

export function HomeworkRow({ homework }: { homework: MyHomeworkListItem }) {
  const overdue = isOverdue(homework);

  return (
    <Link to={`/me/homework/${homework.id}`} className={styles.row}>
      <span className={styles.rowTitle}>{homework.title ?? "Homework"}</span>
      <span className={styles.rowMeta}>
        {overdue ? <span className={styles.overdue}>Overdue</span> : null}
        {homework.status === "assigned" ? <span>{dueLabel(homework.due_on)}</span> : null}
        {homework.status !== "assigned" && homework.submitted_at ? (
          <span>Handed in {formatDateTime(homework.submitted_at)}</span>
        ) : null}
        <StatusChip status={homework.status} />
      </span>
    </Link>
  );
}
