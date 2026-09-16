import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { addedByName } from "@/components/material/authors";
import { TopicsField } from "@/components/topics/TopicsField";
import { taggedTopics } from "@/components/topics/tree";
import { Button, ConfirmDialog, PageHeader, Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { callerRole, useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/format";
import { relationId, useDeleteDocument, useDocument, useRetryDocument, useTagDocument } from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./MaterialDetailPage.module.css";

// One page for both ways in: a student's own material, and the shared library.
export function MaterialDetailPage() {
  const { id, docId } = useParams<{ id: string; docId: string }>();
  const navigate = useNavigate();
  const { user, me } = useAuth();
  const { data: document, isLoading, isError } = useDocument(docId);
  const retry = useRetryDocument();
  const remove = useDeleteDocument();
  const tag = useTagDocument();
  const [confirming, setConfirming] = useState(false);

  const back = id ? { to: `/students/${id}/material`, label: "Material" } : { to: "/library", label: "Library" };
  const fileId = typeof document?.file === "string" ? document.file : (document?.file?.id ?? null);
  // Library material is its author's (or an admin's) to change; a student's material is
  // their tutor's. Directus enforces both — this is only what the page offers.
  const authorId = relationId(document?.user_created);
  const inLibrary = Boolean(document) && relationId(document?.student) === null;
  const canEdit = !inLibrary || callerRole(me) === "admin" || (user !== null && authorId === user.id);

  const tryAgain = async () => {
    if (!docId) {
      return;
    }
    try {
      await retry.mutateAsync(docId);
      toast.success("Reading this material again");
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
      toast.success("Material deleted");
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
            eyebrow={inLibrary ? "Library" : "Material"}
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
              ) : null
            }
            meta={
              <>
                <StatusChip status={document.kind} />
                <StatusChip status={document.status} />
                <span>Added {formatDateTime(document.date_created)}</span>
                {inLibrary ? <span>by {addedByName(document.user_created, user?.id ?? null)}</span> : null}
                {document.source_url ? (
                  <a className={styles.source} href={document.source_url} target="_blank" rel="noreferrer">
                    Open the original page
                  </a>
                ) : null}
              </>
            }
          />

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

          <p className={pageStyles.textBlock}>
            {document.text ??
              (document.status === "ready"
                ? "Nothing could be read from this material."
                : "Nothing has been read from this yet.")}
          </p>

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
                ? "It leaves the library for every tutor. Homework, feedback and plans already generated from it stay as they are."
                : "The material and anything read from it are removed. Homework, feedback and plans already generated from it stay as they are."
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
