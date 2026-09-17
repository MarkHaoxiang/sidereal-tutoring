import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { GenerationProgress } from "@/components/artefacts/GenerationProgress";
import { addedByName } from "@/components/material/authors";
import { ScanView } from "@/components/material/ScanView";
import { TopicsField } from "@/components/topics/TopicsField";
import { taggedTopics } from "@/components/topics/tree";
import { Button, ConfirmDialog, Field, PageHeader, Select, Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { callerRole, useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/format";
import {
  relationId,
  useCreateJob,
  useDeleteDocument,
  useDocument,
  useRetryDocument,
  useTagDocument,
} from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./MaterialDetailPage.module.css";

// Whether the extractor reads the pages as images; Auto leaves the choice to it.
type PagesChoice = "auto" | "yes" | "no";

const PAGES: Record<PagesChoice, boolean | null> = { auto: null, yes: true, no: false };

// One page for both ways in: a student's own material, and the shared library.
export function MaterialDetailPage() {
  const { id, docId } = useParams<{ id: string; docId: string }>();
  const navigate = useNavigate();
  const { user, me } = useAuth();
  const { data: document, isLoading, isError } = useDocument(docId);
  const retry = useRetryDocument();
  const remove = useDeleteDocument();
  const tag = useTagDocument();
  const extract = useCreateJob();
  const [confirming, setConfirming] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pages, setPages] = useState<PagesChoice>("auto");

  const back = id ? { to: `/students/${id}/material`, label: "Material" } : { to: "/library", label: "Library" };
  const fileId = typeof document?.file === "string" ? document.file : (document?.file?.id ?? null);
  // Library material is its author's (or an admin's) to change; a student's material is
  // their tutor's. Directus enforces both — this is only what the page offers.
  const authorId = relationId(document?.user_created);
  const inLibrary = Boolean(document) && relationId(document?.student) === null;
  const canEdit = !inLibrary || callerRole(me) === "admin" || (user !== null && authorId === user.id);

  // A paper is library material, so the extraction is offered here and nowhere else.
  const extractPaper = async () => {
    if (!docId) {
      return;
    }
    try {
      const job = await extract.mutateAsync({
        kind: "paper_extract",
        document_ids: [docId],
        pages: PAGES[pages],
      });
      setJobId(job.id);
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const paperReady = useCallback(
    (paperId: string) => {
      setJobId(null);
      void navigate(`/library/papers/${paperId}`);
    },
    [navigate]
  );

  const tryAgain = async () => {
    if (!docId) {
      return;
    }
    try {
      await retry.mutateAsync(docId);
      toast.success("Reading again");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const deleteMaterial = async () => {
    if (!docId) {
      return;
    }
    try {
      await remove.mutateAsync({ id: docId, fileId });
      toast.success("Deleted");
      void navigate(back.to);
    } catch (error) {
      toast.error(apiError(error));
      throw error;
    }
  };

  return (
    <div>
      {isLoading ? (
        <p className={pageStyles.loading}>
          <Spinner /> Loading material…
        </p>
      ) : null}
      {isError ? <p className={pageStyles.status}>Could not load this material.</p> : null}

      {document ? (
        <>
          <PageHeader
            back={back}
            title={document.title ?? "Untitled material"}
            actions={
              document.status === "failed" && canEdit ? (
                <Button
                  variant="primary"
                  loading={retry.isPending}
                  onClick={() => {
                    void tryAgain();
                  }}
                >
                  Retry
                </Button>
              ) : inLibrary && document.status === "ready" ? (
                <>
                  <Field label="Read page images" className={styles.pages}>
                    <Select
                      value={pages}
                      onChange={(event) => {
                        setPages(event.target.value as PagesChoice);
                      }}
                    >
                      <option value="auto">Auto</option>
                      <option value="yes">Yes</option>
                      <option value="no">No</option>
                    </Select>
                  </Field>
                  <Button
                    variant="primary"
                    loading={extract.isPending}
                    disabled={jobId !== null}
                    onClick={() => {
                      void extractPaper();
                    }}
                  >
                    Extract as paper
                  </Button>
                </>
              ) : null
            }
            meta={
              <>
                <StatusChip status={document.kind} />
                <StatusChip status={document.status} />
                <span>{formatDateTime(document.date_created)}</span>
                {inLibrary ? <span>by {addedByName(document.user_created, user?.id ?? null)}</span> : null}
                {document.source_url ? (
                  <a className={styles.source} href={document.source_url} target="_blank" rel="noreferrer">
                    Open original
                  </a>
                ) : null}
              </>
            }
          />

          {jobId ? (
            <GenerationProgress
              jobId={jobId}
              kind="paper_extract"
              onDone={paperReady}
              onTryAgain={() => {
                setJobId(null);
                void extractPaper();
              }}
            />
          ) : null}

          {document.status === "failed" ? (
            <p className={styles.error}>{document.error ?? "This material could not be read."}</p>
          ) : null}

          <TopicsField
            topics={taggedTopics(document.topics)}
            editable={canEdit}
            onSave={async (topicIds) => {
              await tag.mutateAsync({ id: document.id, topics: topicIds });
            }}
          />

          {document.kind === "scan" ? (
            <ScanView document={document} />
          ) : (
            <p className={pageStyles.textBlock}>
              {document.text ??
                (document.status === "ready" ? "Nothing was read." : "Not read yet.")}
            </p>
          )}

          {canEdit ? (
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

          <ConfirmDialog
            open={confirming}
            onClose={() => {
              setConfirming(false);
            }}
            title="Delete this material?"
            message={
              inLibrary
                ? "It leaves the library for every tutor. Work already generated from it stays."
                : "The material and anything read from it are removed. Work already generated from it stays."
            }
            confirmLabel="Delete"
            danger
            onConfirm={deleteMaterial}
          />
        </>
      ) : null}
    </div>
  );
}
