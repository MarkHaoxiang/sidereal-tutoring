import { Pencil } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Provenance } from "@/components/artefacts/Provenance";
import { addedByName } from "@/components/material/authors";
import { MarkSchemeEditor } from "@/components/papers/MarkSchemeEditor";
import { QuestionsEditor } from "@/components/papers/QuestionsEditor";
import { WorksheetDialog } from "@/components/papers/WorksheetDialog";
import { buildPatch, paperDraft } from "@/components/papers/draft";
import type { PaperDraft } from "@/components/papers/draft";
import { Button, ConfirmDialog, Field, Input, PageHeader, PdfView, SkeletonRows, StatusChip, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { callerRole, useAuth } from "@/lib/auth-context";
import { fileIdOf } from "@/lib/files";
import { formatDateTime } from "@/lib/format";
import {
  relationId,
  useDeletePaper,
  usePaper,
  useRenderPaper,
  useSavePaper,
  useSetPaperStatus,
} from "@/lib/queries";
import type { PaperStatus } from "@/lib/schema";

import pageStyles from "./page.module.css";
import styles from "@/components/papers/papers.module.css";

// Where a paper goes next, and what the button that takes it there says.
const NEXT_STATUS: Record<PaperStatus, { label: string; status: PaperStatus } | null> = {
  draft: { label: "Mark reviewed", status: "reviewed" },
  reviewed: { label: "Archive", status: "archived" },
  archived: null,
};

export function PaperDetailPage() {
  const { paperId } = useParams<{ paperId: string }>();
  const navigate = useNavigate();
  const { user, me } = useAuth();
  const { data: paper, isLoading, isError } = usePaper(paperId);
  const save = useSavePaper();
  const setStatus = useSetPaperStatus();
  const render = useRenderPaper();
  const remove = useDeletePaper();

  const [draft, setDraft] = useState<PaperDraft | null>(null);
  const [baseline, setBaseline] = useState("");
  const [tab, setTab] = useState<"questions" | "scheme">("questions");
  const [renaming, setRenaming] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [asking, setAsking] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const loaded = useRef<string | null>(null);

  // The draft is reloaded when the stored row moves, never while a tutor is mid-edit.
  useEffect(() => {
    if (!paper) {
      return;
    }
    const stamp = `${paper.id}:${paper.date_updated ?? ""}`;
    if (loaded.current === stamp) {
      return;
    }
    loaded.current = stamp;
    const next = paperDraft(paper);
    setDraft(next);
    setBaseline(JSON.stringify(next));
    setProblems([]);
  }, [paper]);

  const dirty = draft !== null && JSON.stringify(draft) !== baseline;
  const busy = save.isPending || render.isPending;
  const authorId = relationId(paper?.user_created);
  const canDelete = callerRole(me) === "admin" || (user !== null && authorId === user.id);
  const next = paper ? NEXT_STATUS[paper.status] : null;
  const renderedPdf = fileIdOf(paper?.rendered_pdf);
  const schemePdf = fileIdOf(paper?.mark_scheme_pdf);

  const edit = (patch: Partial<PaperDraft>) => {
    // What the last Save refused is about the draft as it was, so an edit clears it.
    setProblems([]);
    setDraft((current) => (current === null ? current : { ...current, ...patch }));
  };

  const saveAndRender = async () => {
    if (!paperId || !draft) {
      return;
    }
    const built = buildPatch(draft);
    if (!built.ok) {
      setProblems(built.problems);
      return;
    }
    setProblems([]);
    try {
      await save.mutateAsync({ id: paperId, patch: built.patch });
    } catch (error) {
      toast.error(apiError(error));
      return;
    }
    try {
      await render.mutateAsync(paperId);
      toast.success("Saved and re-rendered");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const rerender = async () => {
    if (!paperId) {
      return;
    }
    try {
      await render.mutateAsync(paperId);
      toast.success("Re-rendered");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const advance = async () => {
    if (!paperId || !next) {
      return;
    }
    try {
      await setStatus.mutateAsync({ id: paperId, status: next.status });
      toast.success(next.status === "reviewed" ? "Marked as reviewed" : "Archived");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const deletePaper = async () => {
    if (!paperId) {
      return;
    }
    try {
      await remove.mutateAsync(paperId);
      toast.success("Paper deleted");
      void navigate("/library/papers");
    } catch (error) {
      toast.error(apiError(error));
      throw error;
    }
  };

  return (
    <div>
      {isLoading ? <SkeletonRows count={3} label="Loading the paper" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load this paper.</p> : null}

      {paper && draft ? (
        <>
          <PageHeader
            back={{ to: "/library/papers", label: "Papers" }}
            eyebrow="Paper"
            title={
              renaming ? (
                <span className={styles.headerActions}>
                  <Input
                    value={draft.title}
                    aria-label="Paper title"
                    autoFocus
                    onChange={(event) => {
                      edit({ title: event.target.value });
                    }}
                  />
                  <Button
                    onClick={() => {
                      setRenaming(false);
                    }}
                  >
                    Done
                  </Button>
                </span>
              ) : (
                <span className={styles.headerActions}>
                  {draft.title || "Untitled paper"}
                  <button
                    type="button"
                    className={styles.tool}
                    aria-label="Change the title"
                    onClick={() => {
                      setRenaming(true);
                    }}
                  >
                    <Pencil size={15} aria-hidden="true" />
                  </button>
                </span>
              )
            }
            actions={
              <div className={styles.headerActions}>
                <Button
                  variant="primary"
                  loading={busy}
                  disabled={!dirty}
                  onClick={() => {
                    void saveAndRender();
                  }}
                >
                  Save and re-render
                </Button>
                {next ? (
                  <Button
                    loading={setStatus.isPending}
                    onClick={() => {
                      void advance();
                    }}
                  >
                    {next.label}
                  </Button>
                ) : null}
              </div>
            }
            meta={
              <>
                <StatusChip status={paper.status} />
                <span>Added {formatDateTime(paper.date_created)}</span>
                <span>by {addedByName(paper.user_created, user?.id ?? null)}</span>
                <Provenance value={paper.generated_from} />
              </>
            }
          />

          <div className={styles.stack}>
            {dirty ? (
              <div className={styles.saveBar}>
                <p className={styles.saveText}>
                  There are changes here that have not been saved yet.
                </p>
                <div className={styles.saveActions}>
                  <Button
                    variant="primary"
                    loading={busy}
                    onClick={() => {
                      void saveAndRender();
                    }}
                  >
                    Save and re-render
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => {
                      setDraft(paperDraft(paper));
                      setProblems([]);
                    }}
                  >
                    Discard
                  </Button>
                </div>
              </div>
            ) : null}

            {problems.length > 0 ? (
              <ul className={styles.problems}>
                {problems.map((problem) => (
                  <li key={problem} className={styles.problem}>
                    {problem}
                  </li>
                ))}
              </ul>
            ) : null}

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
                      edit({ source: event.target.value });
                    }}
                  />
                </Field>
                <Field label="Board">
                  <Input
                    value={draft.board}
                    onChange={(event) => {
                      edit({ board: event.target.value });
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
                      edit({ year: event.target.value });
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
                      edit({ timeMinutes: event.target.value });
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
                      edit({ totalMarks: event.target.value });
                    }}
                  />
                </Field>
                <Field label="Instructions" className={styles.metaWide}>
                  <Textarea
                    rows={2}
                    value={draft.instructions}
                    placeholder="What the paper tells a candidate before question 1."
                    onChange={(event) => {
                      edit({ instructions: event.target.value });
                    }}
                  />
                </Field>
              </div>
            </section>

            <section className={styles.section}>
              <div className={styles.switch} role="tablist" aria-label="Questions or mark scheme">
                <button
                  type="button"
                  role="tab"
                  className={styles.switchButton}
                  aria-selected={tab === "questions"}
                  onClick={() => {
                    setTab("questions");
                  }}
                >
                  Questions
                </button>
                <button
                  type="button"
                  role="tab"
                  className={styles.switchButton}
                  aria-selected={tab === "scheme"}
                  onClick={() => {
                    setTab("scheme");
                  }}
                >
                  Mark scheme
                </button>
              </div>

              {tab === "questions" ? (
                <QuestionsEditor
                  questions={draft.questions}
                  onChange={(questions) => {
                    edit({ questions });
                  }}
                />
              ) : (
                <MarkSchemeEditor
                  scheme={draft.scheme}
                  numbers={draft.questions.map((question) => question.number).filter(Boolean)}
                  onChange={(scheme) => {
                    edit({ scheme });
                  }}
                />
              )}
            </section>

            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <h2 className={styles.sectionTitle}>Printable</h2>
                <div className={styles.headerActions}>
                  <Button
                    onClick={() => {
                      setAsking(true);
                    }}
                  >
                    Make a worksheet
                  </Button>
                  <Button
                    loading={render.isPending}
                    onClick={() => {
                      void rerender();
                    }}
                  >
                    Re-render
                  </Button>
                </div>
              </div>

              {renderedPdf === null && schemePdf === null ? (
                <p className={styles.status}>
                  There are no PDFs yet. Re-render to make them from the structure above.
                </p>
              ) : (
                <div className={styles.pdfs}>
                  {renderedPdf ? (
                    <div className={styles.pdf}>
                      <p className={styles.pdfLabel}>The paper</p>
                      <PdfView fileId={renderedPdf} fallbackName={`${paper.title}.pdf`} />
                    </div>
                  ) : null}
                  {schemePdf ? (
                    <div className={styles.pdf}>
                      <p className={styles.pdfLabel}>The mark scheme</p>
                      <PdfView fileId={schemePdf} fallbackName={`${paper.title} mark scheme.pdf`} />
                    </div>
                  ) : null}
                </div>
              )}
            </section>
          </div>

          {canDelete ? (
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
          ) : null}

          <WorksheetDialog
            open={asking}
            onClose={() => {
              setAsking(false);
            }}
            paperId={paper.id}
            paperTitle={paper.title}
            questions={paper.structure?.questions ?? []}
          />

          <ConfirmDialog
            open={confirming}
            onClose={() => {
              setConfirming(false);
            }}
            title="Delete this paper?"
            message="The paper, its structure and the questions lifted from it are deleted. The material it was read from stays in the library."
            confirmLabel="Delete"
            danger
            onConfirm={deletePaper}
          />
        </>
      ) : null}
    </div>
  );
}
