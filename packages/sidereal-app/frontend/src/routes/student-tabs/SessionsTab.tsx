import { readItems } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { directus } from "@/lib/directus";
import { formatDateTime } from "@/lib/format";

import styles from "./TabList.module.css";

export function SessionsTab({ studentId }: { studentId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["sessions", studentId],
    queryFn: () =>
      directus.request(
        readItems("sessions", {
          filter: { student: { _eq: studentId } },
          sort: ["-scheduled_at"],
        })
      ),
  });

  if (isLoading) {
    return <p className={styles.status}>Loading sessions…</p>;
  }
  if (isError) {
    return <p className={styles.status}>Could not load sessions.</p>;
  }
  if (!data || data.length === 0) {
    return <EmptyState message="No sessions booked yet for this student." />;
  }

  return (
    <ul className={styles.list}>
      {data.map((session) => (
        <li key={session.id} className={styles.item}>
          <span className={styles.itemTitle}>{formatDateTime(session.scheduled_at)}</span>
          <span className={styles.itemMeta}>
            {session.status}
            {session.duration_minutes ? ` · ${session.duration_minutes} min` : ""}
          </span>
          {session.notes ? <p className={styles.itemBody}>{session.notes}</p> : null}
        </li>
      ))}
    </ul>
  );
}
