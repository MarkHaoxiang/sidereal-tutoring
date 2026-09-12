import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { TopicsField } from "@/components/topics/TopicsField";
import { taggedTopics } from "@/components/topics/tree";
import { Button, ConfirmDialog, PageHeader, Spinner, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useDeleteDocument, useDocument, useRetryDocument, useTagDocument } from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./MaterialDetailPage.module.css";

export function MaterialDetailPage() {
  const { id, docId } = useParams<{ id: string; docId: string }>();
  const navigate = useNavigate();
  const { data: document, isLoading, isError } = useDocument(docId);
  const retry = useRetryDocument();
  const remove = useDeleteDocument();
  const tag = useTagDocument();
  const [confirming, setConfirming] = useState(false);

  const backTo = `/students/${id ?? ""}/material`;
  const fileId = typeof document?.file === "string" ? document.file : (document?.file?.id ?? null);

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
      void navigate(backTo);
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
            back={{ to: backTo, label: "Material" }}
            eyebrow="Material"
            title={document.title ?? "Untitled material"}
            actions={
              document.status === "failed" ? (
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
            title="Delete this material?"
            message="The material and anything read from it are removed. Homework, feedback and plans already generated from it stay as they are."
            confirmLabel="Delete"
            danger
            onConfirm={deleteMaterial}
          />
        </>
      ) : null}
    </div>
  );
}
