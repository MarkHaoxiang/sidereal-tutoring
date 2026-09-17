import { Card } from "@/components/ui";
import { hasMarking, marksLabel } from "@/lib/marking";
import type { Marking } from "@/lib/marking";

import styles from "./student.module.css";

export interface MarkSheetProps {
  marking: Marking | null;
  /** What was handed in, box by box, so each mark sits under the answer it is for. */
  answers: string[];
}

function answerFor(answers: string[], number: string): string {
  const index = Number.parseInt(number, 10) - 1;
  return (answers[index] ?? "").trim();
}

export function MarkSheet({ marking, answers }: MarkSheetProps) {
  if (marking === null || !hasMarking(marking)) {
    return null;
  }

  return (
    <Card title="Marks">
      <p className={styles.markTotal}>
        {marksLabel(marking.total_awarded, marking.total_available)}
      </p>
      {marking.questions.length > 0 ? (
        <ul className={styles.markList}>
          {marking.questions.map((question) => {
            const answer = answerFor(answers, question.number);
            return (
              <li key={question.number} className={styles.markRow}>
                <div className={styles.markHead}>
                  <span className={styles.markQuestion}>Q{question.number}</span>
                  <span className={styles.markScore}>
                    {marksLabel(question.marks_awarded, question.marks_available)}
                  </span>
                </div>
                {answer ? (
                  <p className={styles.markAnswer}>{answer}</p>
                ) : (
                  <p className={styles.markBlank}>You left this one blank.</p>
                )}
                {question.comment ? <p className={styles.markComment}>{question.comment}</p> : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {marking.comment ? <p className={styles.markNote}>{marking.comment}</p> : null}
    </Card>
  );
}
