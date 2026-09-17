import { Plus } from "lucide-react";

import { Button } from "@/components/ui";

import { QuestionCard } from "./QuestionCard";
import { emptyQuestion, moved } from "./draft";
import type { PassageDraft, QuestionDraft } from "./draft";
import styles from "./papers.module.css";

export interface QuestionsEditorProps {
  questions: QuestionDraft[];
  /** The paper's passages, so a `passage_ref` block is chosen rather than typed. */
  passages: PassageDraft[];
  /** What an empty list says; a section says something else. */
  empty?: string;
  onChange: (questions: QuestionDraft[]) => void;
}

/** The paper's questions, each set as it will print and each editable in place. */
export function QuestionsEditor({
  questions,
  passages,
  empty = "No questions yet.",
  onChange,
}: QuestionsEditorProps) {
  return (
    <>
      <div className={styles.cards}>
        {questions.map((question, index) => (
          <QuestionCard
            key={question.key}
            question={question}
            index={index}
            count={questions.length}
            passages={passages}
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
        <p className={styles.status}>{empty}</p>
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
