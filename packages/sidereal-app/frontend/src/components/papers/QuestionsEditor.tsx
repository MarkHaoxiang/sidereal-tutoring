import { Plus } from "lucide-react";

import { Button } from "@/components/ui";

import { QuestionCard } from "./QuestionCard";
import { emptyQuestion, moved } from "./draft";
import type { QuestionDraft } from "./draft";
import styles from "./papers.module.css";

export interface QuestionsEditorProps {
  questions: QuestionDraft[];
  onChange: (questions: QuestionDraft[]) => void;
}

/** The paper's questions, each set as it will print and each editable in place. */
export function QuestionsEditor({ questions, onChange }: QuestionsEditorProps) {
  return (
    <>
      <div className={styles.cards}>
        {questions.map((question, index) => (
          <QuestionCard
            key={question.key}
            question={question}
            index={index}
            count={questions.length}
            onChange={(next) => {
              onChange(questions.map((entry, position) => (position === index ? next : entry)));
            }}
            onMove={(delta) => {
              onChange(moved(questions, index, delta));
            }}
            onRemove={() => {
              onChange(questions.filter((_, position) => position !== index));
            }}
          />
        ))}
      </div>

      {questions.length === 0 ? (
        <p className={styles.status}>This paper has no questions yet.</p>
      ) : null}

      <div className={styles.addRow}>
        <Button
          onClick={() => {
            onChange([...questions, emptyQuestion()]);
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add a question
        </Button>
      </div>
    </>
  );
}
