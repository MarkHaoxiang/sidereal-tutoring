import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { AnswerCard } from "@/components/student/AnswerCard";
import { dueLabel, homeworkQuestions, isOverdue } from "@/components/student/homework";
import { TopicChips } from "@/components/topics/TopicChips";
import { taggedTopics } from "@/components/topics/tree";
import { Card, Markdown, PdfView, Spinner, StatusChip } from "@/components/ui";
import { fileIdOf } from "@/lib/files";
import { useMyHomework } from "@/lib/queries";
import studentStyles from "@/components/student/student.module.css";

import styles from "./me.module.css";

export function StudentHomeworkPage() {
  const { id } = useParams<{ id: string }>();
  const { data: homework, isLoading, isError } = useMyHomework(id);

  if (!homework) {
    return (
      <div className={styles.stack}>
        <Link to="/me/homework" className={styles.back}>
          <ArrowLeft size={14} aria-hidden="true" /> Homework
        </Link>
        {isLoading ? (
          <p className={styles.loading}>
            <Spinner /> Loading…
          </p>
        ) : null}
        {isError ? <p className={styles.status}>This homework could not be loaded.</p> : null}
      </div>
    );
  }

  const questions = homeworkQuestions(homework.questions);
  const topics = taggedTopics(homework.topics);
  const isTypst = homework.format === "typst";
  const pdfId = fileIdOf(homework.pdf);

  return (
    <div className={styles.stack}>
      <div>
        <Link to="/me/homework" className={styles.back}>
          <ArrowLeft size={14} aria-hidden="true" /> Homework
        </Link>
        <h1 className={styles.heading}>{homework.title ?? "Homework"}</h1>
        <p className={styles.meta}>
          <StatusChip status={homework.status} />
          {isOverdue(homework) ? <span className={studentStyles.overdue}>Overdue</span> : null}
          <span>{dueLabel(homework.due_on)}</span>
          <TopicChips topics={topics} />
        </p>
      </div>

      {isTypst && pdfId ? (
        <Card>
          <PdfView fileId={pdfId} fallbackName={`${homework.title ?? "homework"}.pdf`} />
        </Card>
      ) : null}

      {isTypst && !pdfId && homework.content ? (
        <Card>
          <p className={styles.quiet}>Your tutor is still preparing the typeset version.</p>
          <pre className={styles.source}>{homework.content}</pre>
        </Card>
      ) : null}

      {!isTypst && homework.content ? (
        <Card>
          <Markdown>{homework.content}</Markdown>
        </Card>
      ) : null}

      {questions.length > 0 ? (
        <Card title="Questions">
          <ol className={styles.questions}>
            {questions.map((question) => (
              <li key={question.id} className={styles.question}>
                {question.text}
              </li>
            ))}
          </ol>
        </Card>
      ) : null}

      <AnswerCard homework={homework} />
    </div>
  );
}
