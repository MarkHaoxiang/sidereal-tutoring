import { readItems } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { directus } from "@/lib/directus";
import { formatDate } from "@/lib/format";

import styles from "./TabList.module.css";

export function HomeworkTab({ studentId }: { studentId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["homework", studentId],
    queryFn: () =>
      directus.request(
        readItems("homework", {
          filter: { student: { _eq: studentId } },
          sort: ["-date_created"],
        })
      ),
  });

  if (isLoading) {
    return <p className={styles.status}>Loading homework…</p>;
  }
  if (isError) {
    return <p className={styles.status}>Could not load homework.</p>;
  }
  if (!data || data.length === 0) {
    return <EmptyState message="No homework has been set for this student yet." />;
  }

  return (
    <ul className={styles.list}>
      {data.map((item) => (
        <li key={item.id} className={styles.item}>
          <span className={styles.itemTitle}>{item.title ?? "Untitled homework"}</span>
          <span className={styles.itemMeta}>
            {item.status} · Due {formatDate(item.due_on)}
          </span>
        </li>
      ))}
    </ul>
  );
}
