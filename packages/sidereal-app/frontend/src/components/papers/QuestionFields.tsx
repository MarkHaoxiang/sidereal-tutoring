import { Plus } from "lucide-react";

import { Button, Field, Input, Textarea } from "@/components/ui";

import { AnswerField } from "./AnswerField";
import { BlocksEditor } from "./BlocksEditor";
import { EditorTools } from "./EditorTools";
import { emptyPart, emptySubPart, moved } from "./draft";
import type { PartDraft, PassageDraft, QuestionDraft, SubPartDraft } from "./draft";
import styles from "./papers.module.css";

export interface QuestionFieldsProps {
  question: QuestionDraft;
  /** What this question is called, for the fields' labels: "question 3". */
  name: string;
  /** The paper's passages, so a `passage_ref` block is chosen rather than typed. */
  passages: PassageDraft[];
  onChange: (next: QuestionDraft) => void;
}

function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((entry, position) => (position === index ? item : entry));
}

function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, position) => position !== index);
}

/** What every node carries below its words: what it is worth, and where the answer goes. */
function MarksAndAnswer({
  value,
  label,
  onChange,
}: {
  value: SubPartDraft;
  label: string;
  onChange: (next: SubPartDraft) => void;
}) {
  return (
    <div className={styles.nodeRow}>
      <Field label="Marks">
        <Input
          type="number"
          min={0}
          step={1}
          value={value.marks}
          aria-label={`${label} marks`}
          onChange={(event) => {
            onChange({ ...value, marks: event.target.value });
          }}
        />
      </Field>
      <AnswerField
        answerLines={value.answerLines}
        answer={value.answer}
        label={label}
        onChange={(next) => {
          onChange({ ...value, ...next });
        }}
      />
    </div>
  );
}

function SubPartRow({
  part,
  index,
  count,
  where,
  passages,
  onChange,
  onMove,
  onRemove,
}: {
  part: SubPartDraft;
  index: number;
  count: number;
  where: string;
  passages: PassageDraft[];
  onChange: (next: SubPartDraft) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}) {
  const name = `${where} (${part.label || String(index + 1)})`;
  return (
    <div className={styles.subPart}>
      <div className={styles.cardHeader}>
        <Field label="Label">
          <Input
            value={part.label}
            placeholder="i"
            aria-label={`${name} label`}
            onChange={(event) => {
              onChange({ ...part, label: event.target.value });
            }}
          />
        </Field>
        <EditorTools label={name} index={index} count={count} onMove={onMove} onRemove={onRemove} />
      </div>
      <Field label="What it asks">
        <Textarea
          rows={2}
          value={part.text}
          aria-label={`${name} text`}
          onChange={(event) => {
            onChange({ ...part, text: event.target.value });
          }}
        />
      </Field>
      <BlocksEditor
        blocks={part.blocks}
        passages={passages}
        label={name}
        onChange={(blocks) => {
          onChange({ ...part, blocks });
        }}
      />
      <MarksAndAnswer value={part} label={name} onChange={onChange} />
    </div>
  );
}

function PartRow({
  part,
  index,
  count,
  where,
  passages,
  onChange,
  onMove,
  onRemove,
}: {
  part: PartDraft;
  index: number;
  count: number;
  where: string;
  passages: PassageDraft[];
  onChange: (next: PartDraft) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}) {
  const name = `${where}, part ${part.label || String(index + 1)}`;
  return (
    <div className={styles.part}>
      <div className={styles.cardHeader}>
        <Field label="Label">
          <Input
            value={part.label}
            placeholder="a"
            aria-label={`${name} label`}
            onChange={(event) => {
              onChange({ ...part, label: event.target.value });
            }}
          />
        </Field>
        <EditorTools label={name} index={index} count={count} onMove={onMove} onRemove={onRemove} />
      </div>
      <Field label="What it asks">
        <Textarea
          rows={2}
          value={part.text}
          aria-label={`${name} text`}
          onChange={(event) => {
            onChange({ ...part, text: event.target.value });
          }}
        />
      </Field>
      <BlocksEditor
        blocks={part.blocks}
        passages={passages}
        label={name}
        onChange={(blocks) => {
          onChange({ ...part, blocks });
        }}
      />
      <MarksAndAnswer
        value={part}
        label={name}
        onChange={(next) => {
          onChange({ ...part, ...next });
        }}
      />

      {part.parts.length > 0 ? (
        <div className={styles.subParts}>
          {part.parts.map((sub, subIndex) => (
            <SubPartRow
              key={sub.key}
              part={sub}
              index={subIndex}
              count={part.parts.length}
              where={name}
              passages={passages}
              onChange={(next) => {
                onChange({ ...part, parts: replaceAt(part.parts, subIndex, next) });
              }}
              onMove={(delta) => {
                onChange({ ...part, parts: moved(part.parts, subIndex, delta) });
              }}
              onRemove={() => {
                onChange({ ...part, parts: removeAt(part.parts, subIndex) });
              }}
            />
          ))}
        </div>
      ) : null}

      <div className={styles.addRow}>
        <Button
          size="sm"
          onClick={() => {
            onChange({ ...part, parts: [...part.parts, emptySubPart()] });
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add a sub-part
        </Button>
      </div>
    </div>
  );
}

/** One question's structure, as the tutor changes it: parts nest one level, `(a)` then `(i)`. */
export function QuestionFields({ question, name, passages, onChange }: QuestionFieldsProps) {
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

      <Field label="Question">
        <Textarea
          rows={3}
          value={question.stem}
          aria-label={`${name} text`}
          onChange={(event) => {
            onChange({ ...question, stem: event.target.value });
          }}
        />
      </Field>

      <BlocksEditor
        blocks={question.blocks}
        passages={passages}
        label={name}
        onChange={(blocks) => {
          onChange({ ...question, blocks });
        }}
      />

      <MarksAndAnswer
        value={{
          key: question.key,
          label: "",
          text: "",
          marks: question.marks,
          answerLines: question.answerLines,
          answer: question.answer,
          blocks: question.blocks,
        }}
        label={name}
        onChange={(next) => {
          onChange({
            ...question,
            marks: next.marks,
            answerLines: next.answerLines,
            answer: next.answer,
          });
        }}
      />

      {question.parts.length > 0 ? (
        <div className={styles.parts}>
          {question.parts.map((part, partIndex) => (
            <PartRow
              key={part.key}
              part={part}
              index={partIndex}
              count={question.parts.length}
              where={name}
              passages={passages}
              onChange={(next) => {
                onChange({ ...question, parts: replaceAt(question.parts, partIndex, next) });
              }}
              onMove={(delta) => {
                onChange({ ...question, parts: moved(question.parts, partIndex, delta) });
              }}
              onRemove={() => {
                onChange({ ...question, parts: removeAt(question.parts, partIndex) });
              }}
            />
          ))}
        </div>
      ) : null}

      <div className={styles.addRow}>
        <Button
          size="sm"
          onClick={() => {
            onChange({ ...question, parts: [...question.parts, emptyPart()] });
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add a part
        </Button>
      </div>

      <p className={styles.hint}>
        Typst markup: <code>$x^2$</code> sets maths, <code>*bold*</code>, <code>_italic_</code>
      </p>
    </div>
  );
}
