import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { AnswerCard } from "@/components/student/AnswerCard";
import { dueLabel, homeworkQuestions, isOverdue } from "@/components/student/homework";
import { MarkSheet } from "@/components/student/MarkSheet";
import { TopicChips } from "@/components/topics/TopicChips";
import { taggedTopics } from "@/components/topics/tree";
import { Card, Markdown, PdfView, Spinner, StatusChip } from "@/components/ui";
import { fileIdOf } from "@/lib/files";
import { readMarking } from "@/lib/marking";
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
        {isError ? (
          <Card>
            <p className={styles.quiet}>Could not load this homework.</p>
            <p className={styles.line}>
              <Link to="/me/homework" className={styles.link}>
                All your homework
              </Link>
            </p>
          </Card>
        ) : null}
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

      <MarkSheet marking={readMarking(homework.marking)} questions={questions} />

      {isTypst && pdfId ? (
        <Card>
          <PdfView fileId={pdfId} fallbackName={`${homework.title ?? "homework"}.pdf`} />
        </Card>
      ) : null}

      {isTypst && !pdfId && homework.content ? (
        <Card>
          <p className={styles.quiet}>Your tutor is still preparing this.</p>
          <pre className={styles.source}>{homework.content}</pre>
        </Card>
      ) : null}

      {!isTypst && homework.content ? (
        <Card>
          <Markdown>{homework.content}</Markdown>
        </Card>
      ) : null}

      <AnswerCard homework={homework} questions={questions} />
    </div>
  );
}
