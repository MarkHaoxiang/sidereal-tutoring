import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui";
import controlStyles from "@/components/ui/control.module.css";
import { apiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import { usePreviewTypst } from "@/lib/queries";
import { TypstError, diagnosticPlace } from "@/lib/typeset";
import type { Diagnostic } from "@/lib/typeset";

import styles from "./artefacts.module.css";

export interface TypstEditorProps {
  content: string;
  /** Saves the source and compiles it, so `pdf` and `compile_error` come back fresh. */
  onSave: (content: string) => Promise<void>;
}

export function TypstEditor({ content, onSave }: TypstEditorProps) {
  const preview = usePreviewTypst();
  const sourceRef = useRef<HTMLTextAreaElement>(null);

  const [draft, setDraft] = useState(content);
  const [pages, setPages] = useState<string[] | null>(null);
  const [previewed, setPreviewed] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [saving, setSaving] = useState(false);

  // A refetch rewrites the row underneath the editor; it follows along unless the tutor has
  // unsaved work in front of them, which is never thrown away.
  const shown = useRef(content);
  useEffect(() => {
    if (shown.current === content) {
      return;
    }
    const previous = shown.current;
    shown.current = content;
    setDraft((current) => (current === previous ? content : current));
  }, [content]);

  const goToLine = (line: number) => {
    const source = sourceRef.current;
    if (!source) {
      return;
    }
    const lines = source.value.split("\n");
    const index = Math.min(Math.max(line, 1), lines.length) - 1;
    const start = lines.slice(0, index).reduce((total, row) => total + row.length + 1, 0);
    source.focus();
    source.setSelectionRange(start, start + (lines[index]?.length ?? 0));
    const lineHeight = Number.parseFloat(getComputedStyle(source).lineHeight) || 20;
    source.scrollTop = Math.max(0, (index - 2) * lineHeight);
  };

  const runPreview = async () => {
    setDiagnostics([]);
    try {
      const rendered = await preview.mutateAsync(draft);
      setPages(rendered);
      setPreviewed(draft);
    } catch (error) {
      if (error instanceof TypstError && error.diagnostics.length > 0) {
        setDiagnostics(error.diagnostics);
        const first = error.diagnostics.find((diagnostic) => diagnostic.line !== null);
        if (first?.line) {
          goToLine(first.line);
        }
        return;
      }
      toast.error(apiError(error));
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSave(draft);
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Content</h2>
        <div className={styles.headerActions}>
          <Button
            loading={preview.isPending}
            onClick={() => {
              void runPreview();
            }}
          >
            Preview
          </Button>
          <Button
            variant="primary"
            loading={saving}
            disabled={draft === content}
            onClick={() => {
              void save();
            }}
          >
            Save
          </Button>
        </div>
      </div>

      {diagnostics.length > 0 ? (
        <div className={styles.problem}>
          <p className={styles.problemNote}>This source did not compile.</p>
          <ul className={styles.diagnostics}>
            {diagnostics.map((diagnostic, index) => {
              const place = diagnosticPlace(diagnostic);
              return (
                <li key={`${String(index)}-${diagnostic.message}`}>
                  <button
                    type="button"
                    className={styles.diagnostic}
                    onClick={() => {
                      if (diagnostic.line !== null) {
                        goToLine(diagnostic.line);
                      }
                    }}
                  >
                    {place ? <span className={styles.diagnosticPlace}>{place}</span> : null}
                    {diagnostic.message}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <div className={styles.typst}>
        <div className={styles.typstPane}>
          <textarea
            ref={sourceRef}
            className={cx(controlStyles.control, controlStyles.textarea, styles.typstSource)}
            value={draft}
            spellCheck={false}
            aria-label="Typst source"
            onChange={(event) => {
              setDraft(event.target.value);
            }}
          />
          <p className={styles.typstHint}>
            <code>#question[…]</code> numbers a question, <code>#answerlines(3)</code> leaves three
            ruled lines to answer on, and maths goes between <code>$…$</code>.
          </p>
        </div>

        <div className={styles.typstPane}>
          {pages === null ? (
            <p className={styles.status}>Choose Preview to see the pages as the student will get them.</p>
          ) : (
            <div className={styles.typstPreview}>
              {pages.map((page, index) => (
                // The SVG comes from this app's own typeset service, which compiles in a world
                // with no files, no packages and no network.
                <div
                  key={index}
                  className={styles.typstPage}
                  dangerouslySetInnerHTML={{ __html: page }}
                />
              ))}
            </div>
          )}
          {pages !== null && previewed !== draft ? (
            <p className={styles.typstStale}>Edited since this preview — choose Preview again.</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
