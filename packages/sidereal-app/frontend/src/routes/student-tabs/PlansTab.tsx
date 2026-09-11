import { Link } from "react-router-dom";

import { GenerateSection } from "@/components/artefacts/GenerateSection";
import styles from "@/components/artefacts/artefacts.module.css";
import { Spinner, StatusChip } from "@/components/ui";
import { formatDate, formatDateTime } from "@/lib/format";
import { usePlans } from "@/lib/queries";

import { useStudentTab } from "./context";

export function PlansTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = usePlans({ studentId });

  return (
    <div>
      {isLoading ? (
        <p className={styles.status}>
          <Spinner /> Loading study plans…
        </p>
      ) : null}
      {isError ? <p className={styles.status}>Could not load study plans.</p> : null}

      {data ? (
        <GenerateSection
          studentId={studentId}
          kind="plan"
          empty={data.length === 0}
          emptyMessage="No study plans yet. Generate one from this student's material."
        />
      ) : null}

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((plan) => (
            <li key={plan.id}>
              <Link to={`/students/${studentId}/plans/${plan.id}`} className={styles.link}>
                <span className={styles.top}>
                  <span className={styles.title}>{plan.title ?? "Untitled study plan"}</span>
                  <StatusChip status={plan.status} />
                </span>
                <span className={styles.meta}>
                  <span>Created {formatDateTime(plan.date_created)}</span>
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
