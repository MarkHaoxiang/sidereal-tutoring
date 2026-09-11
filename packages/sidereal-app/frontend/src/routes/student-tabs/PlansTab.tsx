import { readItems } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { directus } from "@/lib/directus";
import { formatDate } from "@/lib/format";

import styles from "./TabList.module.css";

export function PlansTab({ studentId }: { studentId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["plans", studentId],
    queryFn: () =>
      directus.request(
        readItems("plans", {
          filter: { student: { _eq: studentId } },
          sort: ["-date_created"],
        })
      ),
  });

  if (isLoading) {
    return <p className={styles.status}>Loading plans…</p>;
  }
  if (isError) {
    return <p className={styles.status}>Could not load plans.</p>;
  }
  if (!data || data.length === 0) {
    return <EmptyState message="No study plans have been created for this student yet." />;
  }

  return (
    <ul className={styles.list}>
      {data.map((plan) => (
        <li key={plan.id} className={styles.item}>
          <span className={styles.itemTitle}>{plan.title ?? "Untitled plan"}</span>
          <span className={styles.itemMeta}>
            {plan.status} · {formatDate(plan.period_start)} – {formatDate(plan.period_end)}
          </span>
        </li>
      ))}
    </ul>
  );
}
