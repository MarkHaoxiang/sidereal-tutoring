import { Field, Input, Textarea } from "@/components/ui";

import type { PaperDraft } from "./draft";
import styles from "./papers.module.css";

export interface PaperDetailsProps {
  draft: PaperDraft;
  onChange: (patch: Partial<PaperDraft>) => void;
}

/** What the paper says before question 1: where it came from, how long it is, what to do. */
export function PaperDetails({ draft, onChange }: PaperDetailsProps) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Details</h2>
      </div>
      <div className={styles.meta}>
        <Field label="Source">
          <Input
            value={draft.source}
            placeholder="Where this paper came from"
            onChange={(event) => {
              onChange({ source: event.target.value });
            }}
          />
        </Field>
        <Field label="Board">
          <Input
            value={draft.board}
            onChange={(event) => {
              onChange({ board: event.target.value });
            }}
          />
        </Field>
        <Field label="Year">
          <Input
            type="number"
            min={0}
            step={1}
            value={draft.year}
            onChange={(event) => {
              onChange({ year: event.target.value });
            }}
          />
        </Field>
        <Field label="Time (minutes)">
          <Input
            type="number"
            min={0}
            step={1}
            value={draft.timeMinutes}
            onChange={(event) => {
              onChange({ timeMinutes: event.target.value });
            }}
          />
        </Field>
        <Field label="Total marks">
          <Input
            type="number"
            min={0}
            step={1}
            value={draft.totalMarks}
            onChange={(event) => {
              onChange({ totalMarks: event.target.value });
            }}
          />
        </Field>
        <Field label="Instructions" className={styles.metaWide}>
          <Textarea
            rows={2}
            value={draft.instructions}
            placeholder="What the paper tells a candidate before question 1."
            onChange={(event) => {
              onChange({ instructions: event.target.value });
            }}
          />
        </Field>
      </div>
    </section>
  );
}
