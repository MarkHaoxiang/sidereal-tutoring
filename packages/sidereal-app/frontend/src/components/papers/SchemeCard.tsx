import { Check, Pencil } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";
import { useDebounced } from "@/lib/debounce";
import type { RenderBody } from "@/lib/queries";

import { EditorTools } from "./EditorTools";
import { FragmentView } from "./FragmentView";
import { SchemeFields } from "./SchemeFields";
import { canonicalQuestion, canonicalSchemeQuestion, withoutAnswerLines } from "./draft";
import type { QuestionDraft, SchemeQuestionDraft } from "./draft";
import styles from "./papers.module.css";

const SETTLE_MS = 600;

export interface SchemeCardProps {
  question: SchemeQuestionDraft;
  /** The paper's question of the same number, so the answers are set under what they answer. */
  asked: QuestionDraft | null;
  index: number;
  count: number;
  onChange: (next: SchemeQuestionDraft) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}

/** One entry of the mark scheme: the question, its answers, and the structure behind Edit. */
export function SchemeCard({
  question,
  asked,
  index,
  count,
  onChange,
  onMove,
  onRemove,
}: SchemeCardProps) {
  const [editing, setEditing] = useState(false);

  const name = `mark scheme ${question.number || String(index + 1)}`;
  const scheme = canonicalSchemeQuestion(question, index);
  const answered = asked === null ? null : canonicalQuestion(asked, index);
  const document =
    asked === null
      ? { number: question.number.trim() }
      : answered && withoutAnswerLines(answered);
  const body: RenderBody | null =
    scheme === null || document === null
      ? null
      : { kind: "question", document, mark_scheme: scheme, output: "svg" };
  const settled = useDebounced(body, JSON.stringify(body), SETTLE_MS);

  const parts = question.parts.length;

  return (
    <div className={styles.card}>
      <div className={styles.questionHeader}>
        <h3 className={styles.questionTitle}>
          Mark scheme {question.number || String(index + 1)}
        </h3>
        <p className={styles.questionMeta}>
          {asked === null
            ? "No question on the paper has this number"
            : parts > 0
              ? `${String(parts)} ${parts === 1 ? "part" : "parts"}`
              : "One answer for the whole question"}
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
          empty="This entry needs a number before it can be set."
        />
        {editing ? <SchemeFields question={question} name={name} onChange={onChange} /> : null}
      </div>
    </div>
  );
}
