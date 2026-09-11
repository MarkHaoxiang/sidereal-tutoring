import { readItems } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { directus } from "@/lib/directus";
import { formatDateTime } from "@/lib/format";

import styles from "./TabList.module.css";

export function FeedbackTab({ studentId }: { studentId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["feedback", studentId],
    queryFn: () =>
      directus.request(
        readItems("feedback", {
          filter: { student: { _eq: studentId } },
          sort: ["-date_created"],
        })
      ),
  });

  if (isLoading) {
    return <p className={styles.status}>Loading feedback…</p>;
  }
  if (isError) {
    return <p className={styles.status}>Could not load feedback.</p>;
  }
  if (!data || data.length === 0) {
    return <EmptyState message="No feedback has been written for this student yet." />;
  }

  return (
    <ul className={styles.list}>
      {data.map((item) => (
        <li key={item.id} className={styles.item}>
          <span className={styles.itemMeta}>
            {item.status} · {formatDateTime(item.date_created)}
          </span>
          {item.content ? <p className={styles.itemBody}>{item.content}</p> : null}
        </li>
      ))}
    </ul>
  );
}
