import { Pencil } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Button, ConfirmDialog, Input, Markdown, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import type { GenerationProvenance } from "@/lib/schema";

import { Provenance } from "./Provenance";
import styles from "./artefacts.module.css";

export interface ArtefactDetailProps {
  backTo: string;
  backLabel: string;
  title: string;
  /** Left out where the artefact has no title of its own, as feedback does not. */
  onRename?: (title: string) => Promise<void>;
  /** The status chip and anything else that belongs on the line under the title. */
  meta: ReactNode;
  generatedFrom: GenerationProvenance | null;
  content: string | null;
  emptyContent: string;
  onSaveContent: (content: string) => Promise<void>;
  /** The one step the tutor may take from this status, if there is one. */
  advance?: { label: string; run: () => Promise<void> };
  /** A card to read before the content — what the student handed in. */
  above?: ReactNode;
  /** Fields that belong to this kind alone — a due date, a period. */
  details?: ReactNode;
  /** Anything below the content, such as the questions of a homework. */
  children?: ReactNode;
  deleteTitle: string;
  deleteMessage: string;
  onDelete: () => Promise<void>;
}

export function ArtefactDetail({
  backTo,
  backLabel,
  title,
  onRename,
  meta,
  generatedFrom,
  content,
  emptyContent,
  onSaveContent,
  advance,
  above,
  details,
  children,
  deleteTitle,
  deleteMessage,
  onDelete,
}: ArtefactDetailProps) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(title);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const run = async (action: () => Promise<void>, after: () => void, busy: (value: boolean) => void) => {
    busy(true);
    try {
      await action();
      after();
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      busy(false);
    }
  };

  const saveName = () =>
    run(
      async () => {
        if (onRename) {
          await onRename(name.trim());
        }
      },
      () => {
        setRenaming(false);
      },
      setSaving
    );

  const saveContent = () =>
    run(
      () => onSaveContent(draft),
      () => {
        setEditing(false);
      },
      setSaving
    );

  const takeStep = () =>
    run(
      async () => {
        if (advance) {
          await advance.run();
        }
      },
      () => undefined,
      setAdvancing
    );

  return (
    <div>
      <Link to={backTo} className={styles.back}>
        ← {backLabel}
      </Link>

      <div className={styles.header}>
        <div>
          {renaming ? (
            <div className={styles.renameRow}>
              <Input
                className={styles.renameInput}
                value={name}
                aria-label="Name"
                autoFocus
                onChange={(event) => {
                  setName(event.target.value);
                }}
              />
              <Button
                variant="primary"
                loading={saving}
                onClick={() => {
                  void saveName();
                }}
              >
                Save
              </Button>
              <Button
                variant="ghost"
                disabled={saving}
                onClick={() => {
                  setRenaming(false);
                }}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <div className={styles.titleRow}>
              <h1 className={styles.heading}>{title}</h1>
              {onRename ? (
                <button
                  type="button"
                  className={styles.iconButton}
                  aria-label="Change the name"
                  onClick={() => {
                    setName(title);
                    setRenaming(true);
                  }}
                >
                  <Pencil size={16} aria-hidden="true" />
                </button>
              ) : null}
            </div>
          )}
          <p className={styles.meta}>{meta}</p>
          <Provenance value={generatedFrom} />
        </div>
        {advance && !renaming && !editing ? (
          <Button
            variant="primary"
            loading={advancing}
            onClick={() => {
              void takeStep();
            }}
          >
            {advance.label}
          </Button>
        ) : null}
      </div>

      {above}
      {details}

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Content</h2>
          {editing ? null : (
            <Button
              onClick={() => {
                setDraft(content ?? "");
                setEditing(true);
              }}
            >
              Edit
            </Button>
          )}
        </div>
        {editing ? (
          <>
            <Textarea
              value={draft}
              rows={18}
              aria-label="Content"
              onChange={(event) => {
                setDraft(event.target.value);
              }}
            />
            <div className={styles.editActions}>
              <Button
                variant="primary"
                loading={saving}
                onClick={() => {
                  void saveContent();
                }}
              >
                Save
              </Button>
              <Button
                variant="ghost"
                disabled={saving}
                onClick={() => {
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
            </div>
          </>
        ) : content ? (
          <Markdown>{content}</Markdown>
        ) : (
          <p className={styles.status}>{emptyContent}</p>
        )}
      </section>

      {children}

      <div className={styles.footer}>
        <Button
          variant="danger"
          onClick={() => {
            setConfirming(true);
          }}
        >
          Delete
        </Button>
      </div>

      <ConfirmDialog
        open={confirming}
        onClose={() => {
          setConfirming(false);
        }}
        title={deleteTitle}
        message={deleteMessage}
        confirmLabel="Delete"
        danger
        onConfirm={onDelete}
      />
    </div>
  );
}
