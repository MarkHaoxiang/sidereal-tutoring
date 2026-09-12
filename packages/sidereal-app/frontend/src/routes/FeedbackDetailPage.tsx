import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ArtefactDetail } from "@/components/artefacts/ArtefactDetail";
import { FEEDBACK_NEXT } from "@/components/artefacts/transitions";
import { Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useDeleteFeedback, useFeedback, useUpdateFeedback } from "@/lib/queries";

import pageStyles from "./page.module.css";

export function FeedbackDetailPage() {
  const { id, artefactId } = useParams<{ id: string; artefactId: string }>();
  const navigate = useNavigate();
  const { data: feedback, isLoading, isError } = useFeedback(artefactId);
  const update = useUpdateFeedback();
  const remove = useDeleteFeedback();

  const backTo = `/students/${id ?? ""}/feedback`;

  if (!feedback) {
    return (
      <div>
        <Link to={backTo} className={pageStyles.back}>
          <ArrowLeft size={14} aria-hidden="true" /> Feedback
        </Link>
        {isLoading ? (
          <p className={pageStyles.loading}>
            <Spinner /> Loading feedback…
          </p>
        ) : null}
        {isError ? <p className={pageStyles.status}>Could not load this feedback.</p> : null}
      </div>
    );
  }

  const next = FEEDBACK_NEXT[feedback.status];

  return (
    <ArtefactDetail
      backTo={backTo}
      backLabel="Feedback"
      eyebrow="Feedback"
      title={`Feedback for ${feedback.student?.name ?? "this student"}`}
      meta={
        <>
          <StatusChip status={feedback.status} />
          <span>Written {formatDateTime(feedback.date_created)}</span>
        </>
      }
      generatedFrom={feedback.generated_from}
      content={feedback.content}
      emptyContent="This feedback has no content yet."
      onSaveContent={async (content) => {
        await update.mutateAsync({ id: feedback.id, patch: { content } });
        toast.success("Feedback saved");
      }}
      {...(next
        ? {
            advance: {
              label: next.label,
              run: async () => {
                await update.mutateAsync({ id: feedback.id, patch: { status: next.next } });
                toast.success("Marked as sent");
              },
            },
          }
        : {})}
      deleteTitle="Delete this feedback?"
      deleteMessage="The feedback is removed. The material it came from stays as it is."
      onDelete={async () => {
        try {
          await remove.mutateAsync(feedback.id);
        } catch (error) {
          toast.error(apiError(error));
          throw error;
        }
        toast.success("Feedback deleted");
        void navigate(backTo);
      }}
    />
  );
}
