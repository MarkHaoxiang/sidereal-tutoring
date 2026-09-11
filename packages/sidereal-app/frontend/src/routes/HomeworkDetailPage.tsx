import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ArtefactDetail } from "@/components/artefacts/ArtefactDetail";
import { DueDateField } from "@/components/artefacts/DueDateField";
import { HomeworkQuestions } from "@/components/artefacts/HomeworkQuestions";
import { HOMEWORK_NEXT } from "@/components/artefacts/transitions";
import { Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { useDeleteHomework, useHomework, useUpdateHomework } from "@/lib/queries";

import pageStyles from "./page.module.css";

export function HomeworkDetailPage() {
  const { id, artefactId } = useParams<{ id: string; artefactId: string }>();
  const navigate = useNavigate();
  const { data: homework, isLoading, isError } = useHomework(artefactId);
  const update = useUpdateHomework();
  const remove = useDeleteHomework();

  const backTo = `/students/${id ?? ""}/homework`;

  if (!homework) {
    return (
      <div>
        <Link to={backTo} className={pageStyles.back}>
          ← Homework
        </Link>
        {isLoading ? (
          <p className={pageStyles.loading}>
            <Spinner /> Loading homework…
          </p>
        ) : null}
        {isError ? <p className={pageStyles.status}>Could not load this homework.</p> : null}
      </div>
    );
  }

  const next = HOMEWORK_NEXT[homework.status];

  return (
    <ArtefactDetail
      backTo={backTo}
      backLabel="Homework"
      title={homework.title ?? "Untitled homework"}
      onRename={async (title) => {
        await update.mutateAsync({ id: homework.id, patch: { title: title || null } });
      }}
      meta={
        <>
          <StatusChip status={homework.status} />
          <span>Created {formatDateTime(homework.date_created)}</span>
          {homework.due_on ? <span>Due {formatDate(homework.due_on)}</span> : null}
        </>
      }
      generatedFrom={homework.generated_from}
      content={homework.content}
      emptyContent="This homework has no content yet."
      onSaveContent={async (content) => {
        await update.mutateAsync({ id: homework.id, patch: { content } });
        toast.success("Homework saved");
      }}
      {...(next
        ? {
            advance: {
              label: next.label,
              run: async () => {
                await update.mutateAsync({ id: homework.id, patch: { status: next.next } });
                toast.success(next.label.replace("Mark as", "Marked as"));
              },
            },
          }
        : {})}
      details={
        <DueDateField
          value={homework.due_on}
          onSave={async (due) => {
            await update.mutateAsync({ id: homework.id, patch: { due_on: due } });
          }}
        />
      }
      deleteTitle="Delete this homework?"
      deleteMessage="The homework and its questions are removed. The material it came from stays as it is."
      onDelete={async () => {
        try {
          await remove.mutateAsync(homework.id);
        } catch (error) {
          toast.error(apiError(error));
          throw error;
        }
        toast.success("Homework deleted");
        void navigate(backTo);
      }}
    >
      <HomeworkQuestions homework={homework} />
    </ArtefactDetail>
  );
}
