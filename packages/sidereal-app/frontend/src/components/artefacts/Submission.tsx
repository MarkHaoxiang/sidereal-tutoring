import { Paperclip } from "lucide-react";
import { toast } from "sonner";

import { Button, ConfidenceChip, Markdown, Spinner } from "@/components/ui";
import { apiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import { useFileBlob } from "@/lib/files";
import { formatDateTime } from "@/lib/format";
import { useTranscribeSubmission } from "@/lib/queries";
import type { Transcription } from "@/lib/schema";
import { plainText } from "@/lib/typstText";

import styles from "./artefacts.module.css";

const FALLBACK = "the student's working";

/** A photo shown as it was handed in; anything else as a link to open. */
function Attachment({ fileId }: { fileId: string }) {
  const { url, name, isLoading, error } = useFileBlob(fileId, FALLBACK);

  if (isLoading) {
    return (
      <p className={styles.status}>
        <Spinner size="sm" /> {FALLBACK}
      </p>
    );
  }
  if (error !== null || url === null) {
    return <p className={styles.status}>{error ?? "This file could not be opened."}</p>;
  }
  if (/\.pdf$/i.test(name)) {
    return (
      <p className={styles.attachment}>
        <a className={styles.attachmentLink} href={url} target="_blank" rel="noreferrer">
          <Paperclip size={14} aria-hidden="true" />
          {name}
        </a>
      </p>
    );
  }
  return (
    <a className={styles.photo} href={url} target="_blank" rel="noreferrer">
      <img src={url} alt={name} className={styles.photoImage} />
    </a>
  );
}

export interface SubmissionProps {
  homeworkId: string;
  submittedAt: string | null;
  submission: string | null;
  /** The id of a photo or PDF of the student's working, when they attached one. */
  attachmentId?: string | null;
  /** What the photo says, typed out. */
  transcription?: Transcription | null;
}

/** What the student handed in, above the homework itself — the first thing to read. */
export function Submission({
  homeworkId,
  submittedAt,
  submission,
  attachmentId = null,
  transcription = null,
}: SubmissionProps) {
  const transcribe = useTranscribeSubmission();

  if (!submittedAt && !submission && !attachmentId) {
    return null;
  }

  const read = async () => {
    try {
      await transcribe.mutateAsync(homeworkId);
      toast.success("Typed");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <section className={cx(styles.section, styles.handedIn)}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Handed in</h2>
        <span className={styles.status}>
          {submittedAt ? formatDateTime(submittedAt) : null}
          {attachmentId && !transcription ? (
            <Button
              size="sm"
              loading={transcribe.isPending}
              onClick={() => {
                void read();
              }}
            >
              Transcribe
            </Button>
          ) : null}
        </span>
      </div>
      {submission ? (
        <Markdown>{plainText(submission)}</Markdown>
      ) : (
        <p className={styles.status}>Nothing written.</p>
      )}
      {attachmentId ? <Attachment fileId={attachmentId} /> : null}
      {transcription?.text ? (
        <div className={styles.transcript}>
          <div className={styles.transcriptHeader}>
            <span className={styles.status}>From the photo</span>
            {transcription.confidence ? <ConfidenceChip confidence={transcription.confidence} /> : null}
          </div>
          <Markdown transcribed>{plainText(transcription.text)}</Markdown>
        </div>
      ) : null}
    </section>
  );
}
