import { Card, EmptyState, Markdown, SkeletonRows } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { useMyPlans } from "@/lib/queries";
import type { MyPlan } from "@/lib/queries";

import styles from "./me.module.css";

function period(plan: MyPlan): string | null {
  if (!plan.period_start && !plan.period_end) {
    return null;
  }
  return `${formatDate(plan.period_start)} – ${formatDate(plan.period_end)}`;
}

function PlanBody({ plan }: { plan: MyPlan }) {
  const dates = period(plan);
  return (
    <div>
      <h2 className={styles.planTitle}>{plan.title ?? "Study plan"}</h2>
      {dates ? <p className={styles.subheading}>{dates}</p> : null}
      <div className={styles.planContent}>
        {plan.content ? <Markdown>{plan.content}</Markdown> : <p className={styles.status}>Nothing written yet.</p>}
      </div>
    </div>
  );
}

export function StudentPlanPage() {
  const { data, isLoading, isError } = useMyPlans();

  const plans = data ?? [];
  const active = plans.filter((plan) => plan.status === "active");
  const past = plans.filter((plan) => plan.status === "completed");

  return (
    <div className={styles.stack}>
      <h1 className={styles.heading}>Your study plan</h1>

      {isLoading ? <SkeletonRows count={1} label="Loading your study plan" /> : null}
      {isError ? <p className={styles.status}>Your study plan could not be loaded. Try again in a moment.</p> : null}

      {active.map((plan) => (
        <Card key={plan.id}>
          <PlanBody plan={plan} />
        </Card>
      ))}

      {!isLoading && !isError && active.length === 0 ? (
        <EmptyState message="No study plan running right now. Your tutor will share one when it is ready." />
      ) : null}

      {past.length > 0 ? (
        <details className={styles.past}>
          <summary className={styles.pastSummary}>
            {past.length === 1 ? "1 finished plan" : `${String(past.length)} finished plans`}
          </summary>
          <div className={styles.pastBody}>
            {past.map((plan) => (
              <PlanBody key={plan.id} plan={plan} />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
