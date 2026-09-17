import { Plus } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui";

import { SchemeCard } from "./SchemeCard";
import { emptySchemeQuestion, moved } from "./draft";
import type { PassageDraft, QuestionDraft, SchemeQuestionDraft } from "./draft";
import styles from "./papers.module.css";

export interface MarkSchemeEditorProps {
  scheme: SchemeQuestionDraft[];
  /** The paper's questions, so each entry is set under the question it answers. */
  questions: QuestionDraft[];
  /** The paper's passages, so a question that points at one is set with it. */
  passages: PassageDraft[];
  onChange: (scheme: SchemeQuestionDraft[]) => void;
  /** Shown beside "No mark scheme yet." — the tab's extract action, not this editor's. */
  emptyAction?: ReactNode;
}

/** The answers, numbered to match the paper. It renders as the second PDF. */
export function MarkSchemeEditor({
  scheme,
  questions,
  passages,
  onChange,
  emptyAction,
}: MarkSchemeEditorProps) {
  const numbers = questions.map((question) => question.number.trim()).filter(Boolean);
  const missing = numbers.filter(
    (number) => !scheme.some((question) => question.number.trim() === number)
  );

  return (
    <>
      <div className={styles.cards}>
        {scheme.map((question, index) => (
          <SchemeCard
            key={question.key}
            question={question}
            asked={
              questions.find(
                (entry) =>
                  entry.number.trim() !== "" && entry.number.trim() === question.number.trim()
              ) ?? null
            }
            passages={passages}
            index={index}
            count={scheme.length}
            onChange={(next) => {
              onChange(scheme.map((entry, position) => (position === index ? next : entry)));
            }}
            onMove={(delta) => {
              onChange(moved(scheme, index, delta));
            }}
            onRemove={() => {
              onChange(scheme.filter((_, position) => position !== index));
            }}
          />
        ))}
      </div>

      {scheme.length === 0 ? (
        <p className={styles.status}>
          No mark scheme yet.
          {emptyAction}
        </p>
      ) : null}

      <div className={styles.addRow}>
        <Button
          onClick={() => {
            onChange([...scheme, emptySchemeQuestion()]);
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add an answer
        </Button>
        {missing.length > 0 ? (
          <Button
            onClick={() => {
              onChange([
                ...scheme,
                ...missing.map((number) => ({ ...emptySchemeQuestion(), number })),
              ]);
            }}
          >
            Add missing numbers
          </Button>
        ) : null}
      </div>
    </>
  );
}
