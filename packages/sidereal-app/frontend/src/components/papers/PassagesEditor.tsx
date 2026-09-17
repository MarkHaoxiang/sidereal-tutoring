import { Plus } from "lucide-react";

import { Button, Field, Input, Textarea } from "@/components/ui";

import { EditorTools } from "./EditorTools";
import { emptyPassage, moved } from "./draft";
import type { PassageDraft } from "./draft";
import styles from "./papers.module.css";

export interface PassagesEditorProps {
  passages: PassageDraft[];
  onChange: (passages: PassageDraft[]) => void;
}

/** Extracts printed once after the instructions; a question points at one by its name. */
export function PassagesEditor({ passages, onChange }: PassagesEditorProps) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Passages</h2>
      </div>

      {passages.map((passage, index) => {
        const name = passage.title.trim() || passage.id.trim() || `Passage ${String(index + 1)}`;
        const update = (patch: Partial<PassageDraft>) => {
          onChange(
            passages.map((entry, position) =>
              position === index ? { ...entry, ...patch } : entry
            )
          );
        };
        return (
          <div key={passage.key} className={styles.part}>
            <div className={styles.cardHeader}>
              <Field label="Name" className={styles.passageName}>
                <Input
                  value={passage.id}
                  placeholder="ozymandias"
                  aria-label={`${name} name`}
                  onChange={(event) => {
                    update({ id: event.target.value });
                  }}
                />
              </Field>
              <Field label="Title" className={styles.passageTitle}>
                <Input
                  value={passage.title}
                  aria-label={`${name} title`}
                  onChange={(event) => {
                    update({ title: event.target.value });
                  }}
                />
              </Field>
              <EditorTools
                label={name}
                index={index}
                count={passages.length}
                onMove={(delta) => {
                  onChange(moved(passages, index, delta));
                }}
                onRemove={() => {
                  onChange(passages.filter((_, position) => position !== index));
                }}
              />
            </div>
            <Field label="Text" help="Set line for line, exactly as it is typed.">
              <Textarea
                rows={5}
                value={passage.text}
                aria-label={`${name} text`}
                onChange={(event) => {
                  update({ text: event.target.value });
                }}
              />
            </Field>
          </div>
        );
      })}

      <div className={styles.addRow}>
        <Button
          size="sm"
          onClick={() => {
            onChange([...passages, emptyPassage()]);
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add a passage
        </Button>
      </div>
    </section>
  );
}
