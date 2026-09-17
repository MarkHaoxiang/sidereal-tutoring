import { Link } from "react-router-dom";

import { GenerateSection } from "@/components/artefacts/GenerateSection";
import styles from "@/components/artefacts/artefacts.module.css";
import { SkeletonRows, StatusChip } from "@/components/ui";
import { formatDate, formatDateTime } from "@/lib/format";
import { usePlans } from "@/lib/queries";

import { useStudentTab } from "./context";

export function PlansTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = usePlans({ studentId });

  return (
    <div>
      {isLoading ? <SkeletonRows count={2} label="Loading study plans" /> : null}
      {isError ? <p className={styles.status}>Could not load study plans.</p> : null}

      {data ? (
        <GenerateSection
          studentId={studentId}
          kind="plan"
          empty={data.length === 0}
          emptyMessage="No study plans yet."
        />
      ) : null}

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((plan) => (
            <li key={plan.id}>
              <Link to={`/students/${studentId}/plans/${plan.id}`} className={styles.link}>
                <span className={styles.title}>{plan.title ?? "Untitled study plan"}</span>
                <StatusChip status={plan.status} />
                <span className={styles.meta}>
                  <span>{formatDateTime(plan.date_created)}</span>
                  {plan.period_start || plan.period_end ? (
                    <span>{`${formatDate(plan.period_start)} – ${formatDate(plan.period_end)}`}</span>
                  ) : null}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
