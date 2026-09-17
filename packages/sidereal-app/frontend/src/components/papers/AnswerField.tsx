import { Plus } from "lucide-react";

import { Button, Field, Input, Select, Textarea } from "@/components/ui";
import type { CanonicalAnswerKind } from "@/lib/schema";

import { EditorTools } from "./EditorTools";
import {
  ANSWER_KINDS,
  MAX_ANSWER_HEIGHT_MM,
  MAX_ANSWER_LINES,
  MAX_GRID_COLS,
  MAX_GRID_ROWS,
  MAX_TABLE_COLS,
  MAX_TABLE_ROWS,
  emptyAnswer,
  emptyAnswerOption,
  moved,
} from "./draft";
import type { AnswerDraft } from "./draft";
import styles from "./papers.module.css";

export interface AnswerFieldProps {
  /** The deprecated spelling, read as Lines and rewritten as an answer on the first change. */
  answerLines: string;
  answer: AnswerDraft | null;
  /** What this node is called, for the controls' labels: "question 3". */
  label: string;
  onChange: (next: { answerLines: string; answer: AnswerDraft | null }) => void;
}

function Extent({
  label,
  value,
  max,
  onChange,
}: {
  label: string;
  value: string;
  max: number;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <Input
        type="number"
        min={0}
        max={max}
        step={1}
        value={value}
        aria-label={label}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </Field>
  );
}

/** The space the student writes in: one control, and only the extents that type reads. */
export function AnswerField({ answerLines, answer, label, onChange }: AnswerFieldProps) {
  const current: AnswerDraft | null =
    answer ?? (answerLines.trim() ? { ...emptyAnswer("lines"), lines: answerLines } : null);

  // Any change leaves the deprecated spelling behind; an untouched one is saved as it was read.
  const set = (next: AnswerDraft | null) => {
    onChange({ answerLines: "", answer: next });
  };

  const options = current?.options ?? [];

  return (
    <div className={styles.answer}>
      <div className={styles.numbers}>
        <Field label="Answer space">
          <Select
            value={current?.type ?? ""}
            aria-label={`${label} answer space`}
            onChange={(event) => {
              const type = event.target.value;
              set(type === "" ? null : emptyAnswer(type as CanonicalAnswerKind));
            }}
          >
            <option value="">Not set</option>
            {ANSWER_KINDS.map((kind) => (
              <option key={kind.id} value={kind.id}>
                {kind.label}
              </option>
            ))}
          </Select>
        </Field>

        {current?.type === "lines" ? (
          <Extent
            label="Lines"
            value={current.lines}
            max={MAX_ANSWER_LINES}
            onChange={(lines) => {
              set({ ...current, lines });
            }}
          />
        ) : null}

        {current?.type === "box" || current?.type === "essay" ? (
          <Extent
            label="Height (mm)"
            value={current.heightMm}
            max={MAX_ANSWER_HEIGHT_MM}
            onChange={(heightMm) => {
              set({ ...current, heightMm });
            }}
          />
        ) : null}

        {current?.type === "grid" || current?.type === "table" ? (
          <>
            <Extent
              label="Rows"
              value={current.rows}
              max={current.type === "table" ? MAX_TABLE_ROWS : MAX_GRID_ROWS}
              onChange={(rows) => {
                set({ ...current, rows });
              }}
            />
            <Extent
              label="Columns"
              value={current.cols}
              max={current.type === "table" ? MAX_TABLE_COLS : MAX_GRID_COLS}
              onChange={(cols) => {
                set({ ...current, cols });
              }}
            />
          </>
        ) : null}
      </div>

      {current?.type === "multiple_choice" ? (
        <div className={styles.choices}>
          {options.map((option, index) => (
            <div key={option.key} className={styles.choiceRow}>
              <Field label="Letter">
                <Input
                  value={option.label}
                  placeholder={String.fromCharCode(65 + index)}
                  aria-label={`${label} choice ${String(index + 1)} letter`}
                  onChange={(event) => {
                    set({
                      ...current,
                      options: options.map((entry, position) =>
                        position === index ? { ...entry, label: event.target.value } : entry
                      ),
                    });
                  }}
                />
              </Field>
              <Field label="Choice" className={styles.choiceBody}>
                <Textarea
                  rows={1}
                  value={option.text}
                  aria-label={`${label} choice ${String(index + 1)}`}
                  onChange={(event) => {
                    set({
                      ...current,
                      options: options.map((entry, position) =>
                        position === index ? { ...entry, text: event.target.value } : entry
                      ),
                    });
                  }}
                />
              </Field>
              <EditorTools
                label={`${label} choice ${String(index + 1)}`}
                index={index}
                count={options.length}
                onMove={(delta) => {
                  set({ ...current, options: moved(options, index, delta) });
                }}
                onRemove={() => {
                  set({ ...current, options: options.filter((_, position) => position !== index) });
                }}
              />
            </div>
          ))}
          <div className={styles.addRow}>
            <Button
              size="sm"
              onClick={() => {
                set({ ...current, options: [...options, emptyAnswerOption()] });
              }}
            >
              <Plus size={14} aria-hidden="true" />
              Add a choice
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
