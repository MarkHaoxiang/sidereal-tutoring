import { Card } from "@/components/ui";
import { hasMarking, marksLabel, questionLabel } from "@/lib/marking";
import type { Marking } from "@/lib/marking";

import type { StudentQuestion } from "./homework";
import styles from "./student.module.css";

export interface MarkSheetProps {
  marking: Marking | null;
  questions: StudentQuestion[];
}

function questionText(questions: StudentQuestion[], number: string): string | null {
  const index = Number.parseInt(number, 10) - 1;
  return questions[index]?.text ?? null;
}

export function MarkSheet({ marking, questions }: MarkSheetProps) {
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
          {marking.questions.map((question) => (
            <li key={question.number} className={styles.markRow}>
              <div className={styles.markHead}>
                <span className={styles.markQuestion}>
                  {questionLabel(question.number, questionText(questions, question.number))}
                </span>
                <span className={styles.markScore}>
                  {marksLabel(question.marks_awarded, question.marks_available)}
                </span>
              </div>
              {question.comment ? <p className={styles.markComment}>{question.comment}</p> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {marking.comment ? <p className={styles.markNote}>{marking.comment}</p> : null}
    </Card>
  );
}
