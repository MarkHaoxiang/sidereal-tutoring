import { readItems } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { directus } from "@/lib/directus";
import { formatDateTime } from "@/lib/format";

import styles from "./TabList.module.css";

export function DocumentsTab({ studentId }: { studentId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["documents", studentId],
    queryFn: () =>
      directus.request(
        readItems("documents", {
          filter: { student: { _eq: studentId } },
          sort: ["-date_created"],
        })
      ),
  });

  if (isLoading) {
    return <p className={styles.status}>Loading documents…</p>;
  }
  if (isError) {
    return <p className={styles.status}>Could not load documents.</p>;
  }
  if (!data || data.length === 0) {
    return <EmptyState message="No documents have been added for this student yet." />;
  }

  return (
    <ul className={styles.list}>
      {data.map((document) => (
        <li key={document.id} className={styles.item}>
          <span className={styles.itemTitle}>{document.title ?? "Untitled document"}</span>
          <span className={styles.itemMeta}>
            {document.kind.replace("_", " ")} · {document.status}
          </span>
          <span className={styles.itemMeta}>{formatDateTime(document.date_created)}</span>
          {document.status === "failed" && document.error ? (
            <p className={styles.itemBody}>{document.error}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
