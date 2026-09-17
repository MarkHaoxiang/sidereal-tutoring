import { Check, Pencil } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";
import { useDebounced } from "@/lib/debounce";
import type { RenderBody } from "@/lib/queries";

import { EditorTools } from "./EditorTools";
import { FragmentView } from "./FragmentView";
import { QuestionFields } from "./QuestionFields";
import { fragmentQuestion, questionMarks } from "./draft";
import type { PassageDraft, QuestionDraft } from "./draft";
import styles from "./papers.module.css";

// Long enough that a tutor typing a formula is not compiling on every keystroke, short
// enough that the set question follows the hand that is writing it.
const SETTLE_MS = 600;

export interface QuestionCardProps {
  question: QuestionDraft;
  index: number;
  count: number;
  /** The paper's passages, so a `passage_ref` block is chosen rather than typed. */
  passages: PassageDraft[];
  onChange: (next: QuestionDraft) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}

/** One question of a paper: set as it will print, and its structure behind an Edit toggle. */
export function QuestionCard({
  question,
  index,
  count,
  passages,
  onChange,
  onMove,
  onRemove,
}: QuestionCardProps) {
  const [editing, setEditing] = useState(false);

  const name = `question ${question.number || String(index + 1)}`;
  const fragment = fragmentQuestion(question, index, passages);
  const body: RenderBody | null =
    fragment === null ? null : { kind: "question", document: fragment, output: "svg" };
  const settled = useDebounced(body, JSON.stringify(body), SETTLE_MS);

  const marks = questionMarks(question);
  const parts = question.parts.length;

  return (
    <div className={styles.card}>
      <div className={styles.questionHeader}>
        <h3 className={styles.questionTitle}>Question {question.number || String(index + 1)}</h3>
        <p className={styles.questionMeta}>
          {marks === null ? "No marks set" : `${String(marks)} ${marks === 1 ? "mark" : "marks"}`}
          {parts > 0 ? ` · ${String(parts)} ${parts === 1 ? "part" : "parts"}` : null}
        </p>
        <div className={styles.questionTools}>
          <Button
            size="sm"
            variant={editing ? "primary" : "secondary"}
            onClick={() => {
              setEditing((current) => !current);
            }}
          >
            {editing ? (
              <>
                <Check size={14} aria-hidden="true" />
                Done
              </>
            ) : (
              <>
                <Pencil size={14} aria-hidden="true" />
                Edit
              </>
            )}
          </Button>
          <EditorTools
            label={name}
            index={index}
            count={count}
            onMove={onMove}
            onRemove={onRemove}
          />
        </div>
      </div>

      <div className={styles.cardBody}>
        <FragmentView
          body={settled}
          label={name}
          empty="Needs a number and some text."
        />
        {editing ? (
          <QuestionFields
            question={question}
            name={name}
            passages={passages}
            onChange={onChange}
          />
        ) : null}
      </div>
    </div>
  );
}
