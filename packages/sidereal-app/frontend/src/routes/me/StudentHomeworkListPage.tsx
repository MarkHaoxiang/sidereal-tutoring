import { HomeworkRow } from "@/components/student/HomeworkRow";
import { byDueDate } from "@/components/student/homework";
import { EmptyState, SkeletonRows } from "@/components/ui";
import { useMyHomeworkList } from "@/lib/queries";
import type { MyHomeworkListItem } from "@/lib/queries";

import styles from "./me.module.css";

function section(heading: string, rows: MyHomeworkListItem[]) {
  if (rows.length === 0) {
    return null;
  }
  return (
    <section>
      <h2 className={styles.sectionHeading}>{heading}</h2>
      <ul className={styles.list}>
        {rows.map((row) => (
          <li key={row.id}>
            <HomeworkRow homework={row} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function StudentHomeworkListPage() {
  const { data, isLoading, isError } = useMyHomeworkList();

  const rows = data ?? [];
  const todo = rows.filter((row) => row.status === "assigned").sort(byDueDate);
  const done = rows.filter((row) => row.status !== "assigned");

  return (
    <div className={styles.stack}>
      <h1 className={styles.heading}>Homework</h1>

      {isLoading ? <SkeletonRows count={3} label="Loading your homework" /> : null}
      {isError ? <p className={styles.status}>Your homework could not be loaded. Try again in a moment.</p> : null}

      {section("To do", todo)}
      {section("Handed in", done)}

      {!isLoading && !isError && rows.length === 0 ? (
        <EmptyState message="No homework yet. Enjoy it while it lasts." />
      ) : null}
    </div>
  );
}
