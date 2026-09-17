import { Plus } from "lucide-react";

import { Button, Field, Input, Textarea } from "@/components/ui";

import { EditorTools } from "./EditorTools";
import { QuestionsEditor } from "./QuestionsEditor";
import { emptySection, moved } from "./draft";
import type { PassageDraft, SectionDraft } from "./draft";
import styles from "./papers.module.css";

export interface SectionsEditorProps {
  sections: SectionDraft[];
  /** The paper's passages, so a `passage_ref` block is chosen rather than typed. */
  passages: PassageDraft[];
  onChange: (sections: SectionDraft[]) => void;
  /** Puts a section's questions back into the paper's own list and drops the section. */
  onUngroup: (index: number) => void;
}

/** Questions under their headings: a section's own instructions, and how many to answer. */
export function SectionsEditor({ sections, passages, onChange, onUngroup }: SectionsEditorProps) {
  return (
    <>
      {sections.map((section, index) => {
        const name = section.title.trim() || `Section ${String(index + 1)}`;
        const update = (patch: Partial<SectionDraft>) => {
          onChange(
            sections.map((entry, position) =>
              position === index ? { ...entry, ...patch } : entry
            )
          );
        };
        return (
          <section key={section.key} className={styles.sectionGroup}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>{name}</h2>
              <div className={styles.questionTools}>
                <Button
                  size="sm"
                  onClick={() => {
                    onUngroup(index);
                  }}
                >
                  Ungroup
                </Button>
                <EditorTools
                  label={name}
                  index={index}
                  count={sections.length}
                  onMove={(delta) => {
                    onChange(moved(sections, index, delta));
                  }}
                  onRemove={() => {
                    onChange(sections.filter((_, position) => position !== index));
                  }}
                />
              </div>
            </div>

            <div className={styles.sectionMeta}>
              <Field label="Title">
                <Input
                  value={section.title}
                  placeholder="Section A"
                  aria-label={`${name} title`}
                  onChange={(event) => {
                    update({ title: event.target.value });
                  }}
                />
              </Field>
              <Field label="Answer this many" help="Leave empty for all.">
                <Input
                  type="number"
                  min={1}
                  step={1}
                  value={section.choose}
                  aria-label={`${name} choose`}
                  onChange={(event) => {
                    update({ choose: event.target.value });
                  }}
                />
              </Field>
              <Field label="Instructions">
                <Textarea
                  rows={2}
                  value={section.instructions}
                  aria-label={`${name} instructions`}
                  onChange={(event) => {
                    update({ instructions: event.target.value });
                  }}
                />
              </Field>
            </div>

            <QuestionsEditor
              questions={section.questions}
              passages={passages}
              empty="No questions in this section yet."
              onChange={(questions) => {
                update({ questions });
              }}
            />
          </section>
        );
      })}

      <div className={styles.addRow}>
        <Button
          onClick={() => {
            onChange([...sections, emptySection()]);
          }}
        >
          <Plus size={14} aria-hidden="true" />
          Add a section
        </Button>
      </div>
    </>
  );
}
