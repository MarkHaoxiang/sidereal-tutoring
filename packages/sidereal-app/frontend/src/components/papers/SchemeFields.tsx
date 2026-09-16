import { Plus } from "lucide-react";

import { Button, Field, Input, Textarea } from "@/components/ui";

import { EditorTools } from "./EditorTools";
import { emptySchemePart, moved } from "./draft";
import type { SchemeQuestionDraft } from "./draft";
import styles from "./papers.module.css";

export interface SchemeFieldsProps {
  question: SchemeQuestionDraft;
  /** What this entry is called, for the fields' labels: "mark scheme 3". */
  name: string;
  onChange: (next: SchemeQuestionDraft) => void;
}

function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((entry, position) => (position === index ? item : entry));
}

function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, position) => position !== index);
}

/** One mark scheme entry's structure: the whole-question answer, and one row per part. */
export function SchemeFields({ question, name, onChange }: SchemeFieldsProps) {
  return (
    <div className={styles.fields}>
      <div className={styles.numbers}>
        <Field label="Number">
          <Input
            value={question.number}
            placeholder="1"
            aria-label={`${name} number`}
            onChange={(event) => {
              onChange({ ...question, number: event.target.value });
            }}
          />
        </Field>
      </div>

      <Field label="Answer">
        <Textarea
          rows={2}
          value={question.answer}
          aria-label={`${name} answer`}
          onChange={(event) => {
            onChange({ ...question, answer: event.target.value });
          }}
        />
      </Field>

      <Field label="Notes">
        <Textarea
          rows={2}
          value={question.notes}
          aria-label={`${name} notes`}
          onChange={(event) => {
            onChange({ ...question, notes: event.target.value });
          }}
        />
      </Field>

      {question.parts.length > 0 ? (
        <div className={styles.parts}>
          {question.parts.map((part, partIndex) => {
            const partName = `${name}, part ${part.label || String(partIndex + 1)}`;
            const updatePart = (next: typeof part) => {
              onChange({ ...question, parts: replaceAt(question.parts, partIndex, next) });
            };
            return (
              <div key={part.key} className={styles.part}>
                <div className={styles.cardHeader}>
                  <Field label="Label">
                    <Input
                      value={part.label}
                      placeholder="a"
                      aria-label={`${partName} label`}
                      onChange={(event) => {
                        updatePart({ ...part, label: event.target.value });
                      }}
                    />
                  </Field>
                  <EditorTools
                    label={partName}
                    index={partIndex}
                    count={question.parts.length}
                    onMove={(delta) => {
                      onChange({ ...question, parts: moved(question.parts, partIndex, delta) });
                    }}
                    onRemove={() => {
                      onChange({ ...question, parts: removeAt(question.parts, partIndex) });
                    }}
                  />
                </div>
                <Field label="Answer">
                  <Textarea
                    rows={2}
                    value={part.answer}
                    aria-label={`${partName} answer`}
                    onChange={(event) => {
                      updatePart({ ...part, answer: event.target.value });
                    }}
                  />
                </Field>
                <Field label="Marks" className={styles.narrow}>
                  <Input
                    type="number"
                    min={0}
                    step={1}
                    value={part.marks}
                    aria-label={`${partName} marks`}
                    onChange={(event) => {
                      updatePart({ ...part, marks: event.target.value });
                    }}
                  />
                </Field>
                <Field label="Notes">
                  <Input
                    value={part.notes}
                    aria-label={`${partName} notes`}
                    onChange={(event) => {
                      updatePart({ ...part, notes: event.target.value });
                    }}
                  />
                </Field>
              </div>
            );
          })}
        </div>
      ) : null}

      <div className={styles.addRow}>
        <Button
          size="sm"
          onClick={() => {
            onChange({ ...question, parts: [...question.parts, emptySchemePart()] });
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add a part
        </Button>
      </div>

      <p className={styles.hint}>
        Answers and notes are Typst markup too, so <code>$x = 2$</code> sets as maths. Number each
        one to match the paper.
      </p>
    </div>
  );
}
