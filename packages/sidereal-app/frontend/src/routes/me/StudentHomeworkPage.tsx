import { Link, useParams } from "react-router-dom";

import { AnswerCard } from "@/components/student/AnswerCard";
import { dueLabel, homeworkQuestions, isOverdue } from "@/components/student/homework";
import { Card, Markdown, Spinner, StatusChip } from "@/components/ui";
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
          ← Homework
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

  return (
    <div className={styles.stack}>
      <div>
        <Link to="/me/homework" className={styles.back}>
          ← Homework
        </Link>
        <h1 className={styles.heading}>{homework.title ?? "Homework"}</h1>
        <p className={styles.meta}>
          <StatusChip status={homework.status} />
          {isOverdue(homework) ? <span className={studentStyles.overdue}>Overdue</span> : null}
          <span>{dueLabel(homework.due_on)}</span>
        </p>
      </div>

      {homework.content ? (
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
