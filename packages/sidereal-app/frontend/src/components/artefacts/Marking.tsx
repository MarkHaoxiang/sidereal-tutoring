import { useEffect, useId, useState } from "react";

import { Button, Field, Input, Textarea } from "@/components/ui";
import { markingTotals, marksLabel } from "@/lib/marking";
import type { MarkedQuestion, Marking as MarkingValue } from "@/lib/marking";
import { plainText } from "@/lib/typstText";

import artefact from "./artefacts.module.css";
import styles from "./marking.module.css";

export interface MarkingQuestion {
  id: string;
  number: string;
  text: string | null;
  marks: number | null;
}

export interface MarkingProps {
  questions: MarkingQuestion[];
  /** What has been marked so far, or null for a hand-in nobody has marked yet. */
  marking: MarkingValue | null;
  /** `submitted` is being marked; `marked` is being corrected. */
  status: "submitted" | "marked";
  /** Saves the marks. `finish` also moves the hand-in to marked. */
  onSave: (marking: MarkingValue, finish: boolean) => Promise<void>;
}

interface Row {
  key: string;
  number: string;
  text: string;
  awarded: string;
  available: string;
  comment: string;
}

interface Draft {
  signature: string;
  rows: Row[];
  comment: string;
  awarded: string;
  available: string;
}

function toMarks(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function toText(value: number | null): string {
  return value === null ? "" : String(value);
}

function build(questions: MarkingQuestion[], marking: MarkingValue | null, signature: string): Draft {
  const before = new Map((marking?.questions ?? []).map((question) => [question.number, question] as const));
  const source: MarkingQuestion[] =
    questions.length > 0
      ? questions
      : (marking?.questions ?? []).map((question) => ({
          id: question.number,
          number: question.number,
          text: null,
          marks: question.marks_available,
        }));

  return {
    signature,
    rows: source.map((question, index) => {
      const already = before.get(question.number);
      return {
        key: question.id || `${question.number}-${String(index)}`,
        number: question.number,
        text: plainText(question.text).replace(/\s+/g, " ").trim(),
        awarded: already ? String(already.marks_awarded) : "",
        available: toText(already && already.marks_available > 0 ? already.marks_available : question.marks),
        comment: already?.comment ?? "",
      };
    }),
    comment: marking?.comment ?? "",
    awarded: toText(marking ? marking.total_awarded : null),
    available: toText(marking ? marking.total_available : null),
  };
}

function marked(row: Row): MarkedQuestion {
  const comment = row.comment.trim();
  return {
    number: row.number,
    marks_awarded: toMarks(row.awarded) ?? 0,
    marks_available: toMarks(row.available) ?? 0,
    ...(comment ? { comment } : {}),
  };
}

/** Everything typed, as one string: what "saved" and "since saved" are compared by. */
function typed(draft: Draft): string {
  return JSON.stringify([
    draft.rows.map((row) => [row.number, row.awarded, row.available, row.comment]),
    draft.comment,
    draft.awarded,
    draft.available,
  ]);
}

/** The first mark that cannot be right, said the way a tutor would say it. */
function refuse(draft: Draft): string | null {
  if (draft.rows.length === 0) {
    const awarded = toMarks(draft.awarded);
    const available = toMarks(draft.available);
    if (awarded !== null && awarded < 0) {
      return "A mark cannot be below 0.";
    }
    if (available !== null && available < 0) {
      return "The marks available cannot be below 0.";
    }
    if (awarded !== null && available !== null && awarded > available) {
      return `This is worth ${String(available)} marks, so ${String(awarded)} is too many.`;
    }
    return null;
  }
  for (const row of draft.rows) {
    const awarded = toMarks(row.awarded);
    const available = toMarks(row.available);
    if (awarded !== null && awarded < 0) {
      return `Question ${row.number} cannot be below 0.`;
    }
    if (available !== null && available < 0) {
      return `Question ${row.number} cannot be worth less than 0 marks.`;
    }
    if (awarded !== null && available !== null && awarded > available) {
      return `Question ${row.number} is worth ${String(available)} marks, so ${String(awarded)} is too many.`;
    }
  }
  return null;
}

export function Marking({ questions, marking, status, onSave }: MarkingProps) {
  const base = useId();
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const signature = JSON.stringify([questions, marking]);
  const [draft, setDraft] = useState(() => build(questions, marking, signature));
  const [saved, setSaved] = useState(() => typed(draft));

  if (draft.signature !== signature) {
    const next = build(questions, marking, signature);
    setDraft(next);
    setSaved(typed(next));
  }

  const dirty = typed(draft) !== saved;

  // Marking is typed a question at a time and a tutor reloads to check it is safe. The
  // browser's own warning is the only one a reload or a closed tab will show.
  useEffect(() => {
    if (!dirty) {
      return;
    }
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      window.removeEventListener("beforeunload", warn);
    };
  }, [dirty]);

  const edit = (next: Partial<Draft>) => {
    setProblem(null);
    setDraft((current) => ({ ...current, ...next }));
  };

  const editRow = (key: string, next: Partial<Row>) => {
    setProblem(null);
    setDraft((current) => ({
      ...current,
      rows: current.rows.map((row) => (row.key === key ? { ...row, ...next } : row)),
    }));
  };

  const questionMarks = draft.rows.map(marked);
  const totals =
    draft.rows.length > 0
      ? markingTotals(questionMarks)
      : { awarded: toMarks(draft.awarded) ?? 0, available: toMarks(draft.available) ?? 0 };
  const label = marksLabel(totals.awarded, totals.available);

  const save = async (finish: boolean) => {
    const trouble = refuse(draft);
    if (trouble) {
      setProblem(trouble);
      return;
    }
    const comment = draft.comment.trim();
    const built: MarkingValue = {
      questions: questionMarks,
      total_awarded: totals.awarded,
      total_available: totals.available,
      ...(comment ? { comment } : {}),
    };
    setSaving(true);
    try {
      await onSave(built, finish);
      setSaved(typed(draft));
    } catch {
      // The caller says what went wrong; everything typed stays where it is.
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={artefact.section}>
      <div className={artefact.sectionHeader}>
        <h2 className={artefact.sectionTitle}>Marking</h2>
        <p className={styles.total} aria-live="polite">
          <span className={styles.totalLabel}>Total</span>
          <span className={styles.totalValue}>{label}</span>
          <span className={styles.totalLabel}>marks</span>
        </p>
      </div>

      {draft.rows.length > 0 ? (
        <ol className={styles.rows}>
          {draft.rows.map((row) => {
            const awardedId = `${base}-${row.key}-awarded`;
            const availableId = `${base}-${row.key}-available`;
            const commentId = `${base}-${row.key}-comment`;
            return (
              <li key={row.key} className={styles.row}>
                <div className={styles.head}>
                  <span className={styles.number}>{row.number}</span>
                  {row.text ? (
                    <p className={styles.text} title={row.text}>
                      {row.text}
                    </p>
                  ) : null}
                </div>
                <div className={styles.marks}>
                  <label className={styles.hidden} htmlFor={awardedId}>
                    Marks for question {row.number}
                  </label>
                  <Input
                    id={awardedId}
                    className={styles.mark}
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="any"
                    value={row.awarded}
                    onChange={(event) => {
                      editRow(row.key, { awarded: event.target.value });
                    }}
                  />
                  <span className={styles.slash} aria-hidden="true">
                    /
                  </span>
                  <label className={styles.hidden} htmlFor={availableId}>
                    Marks available for question {row.number}
                  </label>
                  <Input
                    id={availableId}
                    className={styles.mark}
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="any"
                    value={row.available}
                    onChange={(event) => {
                      editRow(row.key, { available: event.target.value });
                    }}
                  />
                </div>
                <label className={styles.hidden} htmlFor={commentId}>
                  Comment on question {row.number}
                </label>
                <Textarea
                  id={commentId}
                  className={styles.comment}
                  rows={1}
                  placeholder="Comment"
                  value={row.comment}
                  onChange={(event) => {
                    editRow(row.key, { comment: event.target.value });
                  }}
                />
              </li>
            );
          })}
        </ol>
      ) : (
        <div className={styles.solo}>
          <Field label="Marks given">
            <Input
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              value={draft.awarded}
              onChange={(event) => {
                edit({ awarded: event.target.value });
              }}
            />
          </Field>
          <Field label="Out of">
            <Input
              type="number"
              inputMode="decimal"
              min={0}
              step="any"
              value={draft.available}
              onChange={(event) => {
                edit({ available: event.target.value });
              }}
            />
          </Field>
        </div>
      )}

      <Field label="Comment" className={styles.overall}>
        <Textarea
          rows={3}
          value={draft.comment}
          onChange={(event) => {
            edit({ comment: event.target.value });
          }}
        />
      </Field>

      {problem ? (
        <p className={styles.problem} role="alert">
          {problem}
        </p>
      ) : null}

      <div className={styles.actions}>
        {dirty ? (
          <p className={styles.unsaved} aria-live="polite">
            Unsaved marks
          </p>
        ) : null}
        {status === "submitted" ? (
          <Button
            loading={saving}
            onClick={() => {
              void save(false);
            }}
          >
            Save marks
          </Button>
        ) : null}
        <Button
          variant="primary"
          loading={saving}
          onClick={() => {
            void save(status === "submitted");
          }}
        >
          {status === "submitted" ? "Finish marking" : "Save marking"}
        </Button>
      </div>
    </section>
  );
}
