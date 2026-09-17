import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { ArtefactDetail } from "@/components/artefacts/ArtefactDetail";
import { DueDateField } from "@/components/artefacts/DueDateField";
import { HomeworkQuestions } from "@/components/artefacts/HomeworkQuestions";
import { Marking } from "@/components/artefacts/Marking";
import type { MarkingQuestion } from "@/components/artefacts/Marking";
import { Submission } from "@/components/artefacts/Submission";
import { HOMEWORK_NEXT } from "@/components/artefacts/transitions";
import { TypstCard } from "@/components/artefacts/TypstCard";
import { TypstEditor } from "@/components/artefacts/TypstEditor";
import { TypstSource } from "@/components/artefacts/TypstSource";
import { markedQuestions, paperOf } from "@/components/artefacts/questions";
import { TopicsField } from "@/components/topics/TopicsField";
import { taggedTopics } from "@/components/topics/tree";
import { Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { fileIdOf } from "@/lib/files";
import { formatDateTime, relativeDay } from "@/lib/format";
import { readMarking } from "@/lib/marking";
import {
  useCompileHomework,
  useDeleteHomework,
  useFeedbackForHomework,
  useHomework,
  useSaveMarking,
  useTagHomework,
  useUpdateHomework,
} from "@/lib/queries";

import pageStyles from "./page.module.css";

export function HomeworkDetailPage() {
  const { id, artefactId } = useParams<{ id: string; artefactId: string }>();
  const navigate = useNavigate();
  const { data: homework, isLoading, isError } = useHomework(artefactId);
  const feedback = useFeedbackForHomework(artefactId);
  const update = useUpdateHomework();
  const saveMarking = useSaveMarking();
  const remove = useDeleteHomework();
  const compile = useCompileHomework();
  const tag = useTagHomework();

  const backTo = `/students/${id ?? ""}/homework`;

  if (!homework) {
    return (
      <div>
        <Link to={backTo} className={pageStyles.back}>
          <ArrowLeft size={14} aria-hidden="true" /> Homework
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
  const isTypst = homework.format === "typst";
  const pdfId = fileIdOf(homework.pdf);
  const handedInFileId = fileIdOf(homework.submission_file);
  const topics = taggedTopics(homework.topics);
  // Marking replaces the status step it used to be: the panel's own button finishes it.
  const marks = homework.status === "submitted" || homework.status === "marked";
  const advance = marks ? undefined : next;
  const questions: MarkingQuestion[] = markedQuestions(homework.questions);
  const paperId = paperOf(homework.generated_from);
  const written = feedback.data?.[0];

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
          <span>{formatDateTime(homework.date_created)}</span>
          {homework.due_on ? <span>Due {relativeDay(homework.due_on)}</span> : null}
          {isTypst ? <span>Typeset</span> : null}
          {written ? <Link to={`/students/${id ?? ""}/feedback/${written.id}`}>Feedback</Link> : null}
        </>
      }
      generatedFrom={homework.generated_from}
      content={homework.content}
      emptyContent="No content yet."
      onSaveContent={async (content) => {
        await update.mutateAsync({ id: homework.id, patch: { content } });
        toast.success("Saved");
      }}
      {...(isTypst
        ? {
            contentSection: paperId ? (
              <TypstSource content={homework.content ?? ""} paperId={paperId} />
            ) : (
              <TypstEditor
                content={homework.content ?? ""}
                onSave={async (content) => {
                  await update.mutateAsync({ id: homework.id, patch: { content } });
                  await compile.mutateAsync(homework.id);
                  toast.success("Saved");
                }}
              />
            ),
          }
        : {})}
      {...(advance
        ? {
            advance: {
              label: advance.label,
              run: async () => {
                await update.mutateAsync({ id: homework.id, patch: { status: advance.next } });
                toast.success(advance.done);
              },
            },
          }
        : {})}
      above={
        <>
          <Submission
            homeworkId={homework.id}
            submittedAt={homework.submitted_at}
            submission={homework.submission}
            attachmentId={handedInFileId}
            transcription={homework.submission_transcription}
          />
          {marks ? (
            <Marking
              questions={questions}
              marking={readMarking(homework.marking)}
              status={homework.status === "marked" ? "marked" : "submitted"}
              onSave={async (marking, finish) => {
                await saveMarking.mutateAsync({
                  id: homework.id,
                  marking,
                  ...(finish ? { status: "marked" as const } : {}),
                });
                toast.success(finish ? "Marked" : "Marks saved");
              }}
            />
          ) : null}
          {isTypst ? (
            <TypstCard
              homeworkId={homework.id}
              pdfId={pdfId}
              pdfName={`${homework.title ?? "homework"}.pdf`}
              compileError={homework.compile_error}
              compilable={paperId === null}
            />
          ) : null}
        </>
      }
      details={
        <>
          <TopicsField
            topics={topics}
            onSave={async (topicIds) => {
              await tag.mutateAsync({ id: homework.id, topics: topicIds });
            }}
          />
          <DueDateField
            value={homework.due_on}
            onSave={async (due) => {
              await update.mutateAsync({ id: homework.id, patch: { due_on: due } });
            }}
          />
        </>
      }
      deleteTitle="Delete this homework?"
      deleteMessage="The homework and its questions are removed. The material it came from stays."
      onDelete={async () => {
        try {
          await remove.mutateAsync(homework.id);
        } catch (error) {
          toast.error(apiError(error));
          throw error;
        }
        toast.success("Deleted");
        void navigate(backTo);
      }}
    >
      <HomeworkQuestions homework={homework} />
    </ArtefactDetail>
  );
}
