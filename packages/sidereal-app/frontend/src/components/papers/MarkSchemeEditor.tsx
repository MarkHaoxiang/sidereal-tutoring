import { Plus } from "lucide-react";

import { Button, Field, Input, Textarea } from "@/components/ui";

import { EditorTools } from "./EditorTools";
import { emptySchemePart, emptySchemeQuestion, moved } from "./draft";
import type { SchemeQuestionDraft } from "./draft";
import styles from "./papers.module.css";

export interface MarkSchemeEditorProps {
  scheme: SchemeQuestionDraft[];
  /** The question numbers on the paper, so a scheme can be started to match them. */
  numbers: string[];
  onChange: (scheme: SchemeQuestionDraft[]) => void;
}

function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((entry, position) => (position === index ? item : entry));
}

function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, position) => position !== index);
}

/** The answers, numbered to match the paper. It renders as the second PDF. */
export function MarkSchemeEditor({ scheme, numbers, onChange }: MarkSchemeEditorProps) {
  const missing = numbers.filter((number) => !scheme.some((question) => question.number === number));

  return (
    <>
      <p className={styles.hint}>
        Answers and notes are Typst markup too, so <code>$x = 2$</code> sets as maths. Number each one
        to match the paper.
      </p>

      <div className={styles.cards}>
        {scheme.map((question, index) => {
          const name = `mark scheme ${question.number || String(index + 1)}`;
          const update = (next: SchemeQuestionDraft) => {
            onChange(replaceAt(scheme, index, next));
          };
          return (
            <div key={question.key} className={styles.card}>
              <div className={styles.cardHeader}>
                <Field label="Number">
                  <Input
                    value={question.number}
                    placeholder="1"
                    aria-label={`${name} number`}
                    onChange={(event) => {
                      update({ ...question, number: event.target.value });
                    }}
                  />
                </Field>
                <EditorTools
                  label={name}
                  index={index}
                  count={scheme.length}
                  onMove={(delta) => {
                    onChange(moved(scheme, index, delta));
                  }}
                  onRemove={() => {
                    onChange(removeAt(scheme, index));
                  }}
                />
              </div>

              <Field label="Answer">
                <Textarea
                  rows={2}
                  value={question.answer}
                  aria-label={`${name} answer`}
                  onChange={(event) => {
                    update({ ...question, answer: event.target.value });
                  }}
                />
              </Field>

              <Field label="Notes">
                <Textarea
                  rows={2}
                  value={question.notes}
                  aria-label={`${name} notes`}
                  onChange={(event) => {
                    update({ ...question, notes: event.target.value });
                  }}
                />
              </Field>

              {question.parts.length > 0 ? (
                <div className={styles.parts}>
                  {question.parts.map((part, partIndex) => {
                    const partName = `${name}, part ${part.label || String(partIndex + 1)}`;
                    const updatePart = (next: typeof part) => {
                      update({ ...question, parts: replaceAt(question.parts, partIndex, next) });
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
                              update({ ...question, parts: moved(question.parts, partIndex, delta) });
                            }}
                            onRemove={() => {
                              update({ ...question, parts: removeAt(question.parts, partIndex) });
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
                    update({ ...question, parts: [...question.parts, emptySchemePart()] });
                  }}
                >
                  <Plus size={14} aria-hidden="true" />
                  Add a part
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {scheme.length === 0 ? (
        <p className={styles.status}>There is no mark scheme yet.</p>
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
            Add the missing numbers
          </Button>
        ) : null}
      </div>
    </>
  );
}
