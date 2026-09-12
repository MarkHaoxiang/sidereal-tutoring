import { useState } from "react";
import { toast } from "sonner";

import { Button, Card, ConfirmDialog, Field, FileLink, Input, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { fileIdOf } from "@/lib/files";
import { formatDateTime } from "@/lib/format";
import {
  useAttachSubmissionFile,
  useHandInHomework,
  useRemoveSubmissionFile,
  useSaveAnswers,
} from "@/lib/queries";
import type { MyHomework } from "@/lib/queries";

import styles from "./student.module.css";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.heic,.webp";

export function AnswerCard({ homework }: { homework: MyHomework }) {
  const saved = homework.submission ?? "";
  const attachmentId = fileIdOf(homework.submission_file);
  const [answers, setAnswers] = useState(saved);
  const [confirming, setConfirming] = useState(false);
  // A file input cannot be cleared by state; remounting it is what empties it.
  const [inputGeneration, setInputGeneration] = useState(0);
  const save = useSaveAnswers();
  const handIn = useHandInHomework();
  const attach = useAttachSubmissionFile();
  const detach = useRemoveSubmissionFile();

  // Assigned is the only status a student may write in; Directus enforces that, and the
  // page agrees with it rather than offering a control that would be refused.
  if (homework.status !== "assigned") {
    return (
      <Card title="Your answers">
        <div className={styles.answers}>
          <p className={styles.handedIn}>
            {homework.submitted_at
              ? `You handed this in on ${formatDateTime(homework.submitted_at)}.`
              : "This has been handed in."}
            {homework.status === "marked" ? " Your tutor has marked it." : " Your tutor has not marked it yet."}
          </p>
          {saved ? (
            <p className={styles.written}>{saved}</p>
          ) : (
            <p className={styles.handedIn}>You handed this in without writing anything.</p>
          )}
          {attachmentId ? (
            <p className={styles.attachment}>
              <FileLink fileId={attachmentId} fallbackName="your working" />
            </p>
          ) : null}
        </div>
      </Card>
    );
  }

  const saveDraft = async () => {
    try {
      await save.mutateAsync({ id: homework.id, submission: answers });
      toast.success("Draft saved");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const addFile = async (file: File) => {
    try {
      await attach.mutateAsync({ id: homework.id, file });
      toast.success("File attached");
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setInputGeneration((generation) => generation + 1);
    }
  };

  const removeFile = async () => {
    try {
      await detach.mutateAsync({ id: homework.id, fileId: attachmentId });
      toast.success("File removed");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <Card title="Your answers">
      <div className={styles.answers}>
        <Field
          label="Write your answers"
          help="Save a draft as often as you like. Hand in when you are done — after that your answers cannot be changed."
        >
          <Textarea
            rows={10}
            value={answers}
            onChange={(event) => {
              setAnswers(event.target.value);
            }}
          />
        </Field>

        <Field label="Attach a file (photo or PDF of your working)" help="Optional — one file.">
          {attachmentId ? (
            <p className={styles.attachment}>
              <FileLink fileId={attachmentId} fallbackName="your working" />
              <Button
                variant="ghost"
                size="sm"
                loading={detach.isPending}
                onClick={() => {
                  void removeFile();
                }}
              >
                Remove
              </Button>
            </p>
          ) : (
            <Input
              key={`file-${String(inputGeneration)}`}
              type="file"
              accept={ACCEPT}
              className={styles.fileInput}
              disabled={attach.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  void addFile(file);
                }
              }}
            />
          )}
        </Field>

        <div className={styles.actions}>
          <Button
            variant="primary"
            disabled={answers.trim() === "" && attachmentId === null}
            onClick={() => {
              setConfirming(true);
            }}
          >
            Hand in
          </Button>
          <Button
            loading={save.isPending}
            disabled={answers === saved}
            onClick={() => {
              void saveDraft();
            }}
          >
            Save draft
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirming}
        onClose={() => {
          setConfirming(false);
        }}
        title="Hand this homework in?"
        message="Your tutor will see your answers, and you will not be able to change them afterwards."
        confirmLabel="Hand in"
        cancelLabel="Not yet"
        onConfirm={async () => {
          try {
            await handIn.mutateAsync({ id: homework.id, submission: answers });
          } catch (error) {
            toast.error(apiError(error));
            throw error;
          }
          toast.success("Handed in");
        }}
      />
    </Card>
  );
}
