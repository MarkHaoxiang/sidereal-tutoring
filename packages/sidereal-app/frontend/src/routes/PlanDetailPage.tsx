import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ArtefactDetail } from "@/components/artefacts/ArtefactDetail";
import { PLAN_NEXT } from "@/components/artefacts/transitions";
import { Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { useDeletePlan, usePlan, useUpdatePlan } from "@/lib/queries";

import pageStyles from "./page.module.css";

export function PlanDetailPage() {
  const { id, artefactId } = useParams<{ id: string; artefactId: string }>();
  const navigate = useNavigate();
  const { data: plan, isLoading, isError } = usePlan(artefactId);
  const update = useUpdatePlan();
  const remove = useDeletePlan();

  const backTo = `/students/${id ?? ""}/plans`;

  if (!plan) {
    return (
      <div>
        <Link to={backTo} className={pageStyles.back}>
          ← Study plans
        </Link>
        {isLoading ? (
          <p className={pageStyles.loading}>
            <Spinner /> Loading study plan…
          </p>
        ) : null}
        {isError ? <p className={pageStyles.status}>Could not load this study plan.</p> : null}
      </div>
    );
  }

  const next = PLAN_NEXT[plan.status];

  return (
    <ArtefactDetail
      backTo={backTo}
      backLabel="Study plans"
      title={plan.title ?? "Untitled study plan"}
      onRename={async (title) => {
        await update.mutateAsync({ id: plan.id, patch: { title: title || null } });
      }}
      meta={
        <>
          <StatusChip status={plan.status} />
          <span>Created {formatDateTime(plan.date_created)}</span>
          {plan.period_start || plan.period_end ? (
            <span>{`${formatDate(plan.period_start)} – ${formatDate(plan.period_end)}`}</span>
          ) : null}
        </>
      }
      generatedFrom={plan.generated_from}
      content={plan.content}
      emptyContent="This study plan has no content yet."
      onSaveContent={async (content) => {
        await update.mutateAsync({ id: plan.id, patch: { content } });
        toast.success("Study plan saved");
      }}
      {...(next
        ? {
            advance: {
              label: next.label,
              run: async () => {
                await update.mutateAsync({ id: plan.id, patch: { status: next.next } });
                toast.success(next.label.replace("Mark as", "Marked as"));
              },
            },
          }
        : {})}
      deleteTitle="Delete this study plan?"
      deleteMessage="The study plan is removed. The material it came from stays as it is."
      onDelete={async () => {
        try {
          await remove.mutateAsync(plan.id);
        } catch (error) {
          toast.error(apiError(error));
          throw error;
        }
        toast.success("Study plan deleted");
        void navigate(backTo);
      }}
    />
  );
}
