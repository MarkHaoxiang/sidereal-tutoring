import { Camera, Paperclip } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, Card, ConfirmDialog, Field, Spinner, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { fileIdOf, useFileBlob } from "@/lib/files";
import { formatDateTime } from "@/lib/format";
import {
  useAttachSubmissionFile,
  useHandInHomework,
  useRemoveSubmissionFile,
  useSaveAnswers,
  useTranscribeSubmission,
} from "@/lib/queries";
import type { MyHomework } from "@/lib/queries";
import { hasTranscription, readTranscription } from "@/lib/transcription";
import { plainText } from "@/lib/typstText";

import { joinAnswers, splitAnswers } from "./answers";
import type { StudentQuestion } from "./homework";
import { TranscriptionPanel } from "./Transcription";
import styles from "./student.module.css";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.heic,.webp";
const FALLBACK = "your working";

/** The photo as it was taken; anything else as a link to open. */
function Attachment({ fileId }: { fileId: string }) {
  const { url, name, isLoading, error } = useFileBlob(fileId, FALLBACK);

  if (isLoading) {
    return (
      <p className={styles.fileStatus}>
        <Spinner size="sm" /> {FALLBACK}
      </p>
    );
  }
  if (error !== null || url === null) {
    return <p className={styles.fileStatus}>{error ?? "This file could not be opened."}</p>;
  }
  if (/\.pdf$/i.test(name)) {
    return (
      <a className={styles.fileLink} href={url} target="_blank" rel="noreferrer">
        <Paperclip size={14} aria-hidden="true" />
        {name}
      </a>
    );
  }
  return (
    <a className={styles.photo} href={url} target="_blank" rel="noreferrer">
      <img src={url} alt={name} className={styles.photoImage} />
    </a>
  );
}

interface AnswerBoxProps {
  label: string;
  question: string | null;
  value: string;
  onChange: (value: string) => void;
  onCaret: (at: number) => void;
}

/** One box, as tall as what is in it. */
function AnswerBox({ label, question, value, onChange, onCaret }: AnswerBoxProps) {
  const wrapper = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    const box = wrapper.current?.querySelector("textarea");
    if (box) {
      box.style.height = "auto";
      // scrollHeight stops at the padding edge, and the box is border-box.
      const border = box.offsetHeight - box.clientHeight;
      box.style.height = `${String(box.scrollHeight + border)}px`;
    }
  }, [value]);

  return (
    <div ref={wrapper}>
      <Field label={label}>
        {question === null ? null : <p className={styles.questionText}>{question}</p>}
        <Textarea
          rows={4}
          value={value}
          onFocus={(event) => {
            onCaret(event.currentTarget.selectionStart);
          }}
          onSelect={(event) => {
            onCaret(event.currentTarget.selectionStart);
          }}
          onChange={(event) => {
            onCaret(event.currentTarget.selectionStart);
            onChange(event.currentTarget.value);
          }}
        />
      </Field>
    </div>
  );
}

export interface AnswerCardProps {
  homework: MyHomework;
  questions: StudentQuestion[];
}

export function AnswerCard({ homework, questions }: AnswerCardProps) {
  const saved = homework.submission ?? "";
  const attachmentId = fileIdOf(homework.submission_file);
  const transcription = readTranscription(homework.submission_transcription);
  const [parts, setParts] = useState(() => splitAnswers(saved, questions));
  const [confirming, setConfirming] = useState(false);
  const [restore, setRestore] = useState<{ index: number; at: number } | null>(null);
  const caret = useRef<{ index: number; at: number } | null>(null);
  const boxes = useRef<HTMLDivElement | null>(null);
  const save = useSaveAnswers();
  const handIn = useHandInHomework();
  const attach = useAttachSubmissionFile();
  const detach = useRemoveSubmissionFile();
  const transcribe = useTranscribeSubmission();

  useEffect(() => {
    if (restore === null) {
      return;
    }
    const box = boxes.current?.querySelectorAll("textarea")[restore.index];
    if (box) {
      box.focus();
      box.setSelectionRange(restore.at, restore.at);
    }
    setRestore(null);
  }, [restore]);

  const readFile = async () => {
    try {
      await transcribe.mutateAsync(homework.id);
      toast.success("Typed");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const removeFile = async () => {
    try {
      await detach.mutateAsync({ id: homework.id, fileId: attachmentId });
      toast.success("Removed");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const attachment =
    attachmentId === null ? null : (
      <div className={styles.attachment}>
        <Attachment fileId={attachmentId} />
        {homework.status === "assigned" ? (
          <div className={styles.actions}>
            <Button
              size="sm"
              loading={transcribe.isPending}
              onClick={() => {
                void readFile();
              }}
            >
              Transcribe
            </Button>
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
          </div>
        ) : null}
      </div>
    );

  // Assigned is the only status a student may write in; Directus enforces that, and the
  // page agrees with it rather than offering a control that would be refused.
  if (homework.status !== "assigned") {
    return (
      <Card title="Your answers">
        <div className={styles.answers}>
          <p className={styles.handedIn}>
            {homework.submitted_at
              ? `Submitted ${formatDateTime(homework.submitted_at)}.`
              : "Submitted."}
            {homework.status === "marked" ? " Marked." : " Not marked yet."}
          </p>
          {questions.length > 0 ? (
            questions.map((question, index) => (
              <div key={question.id} className={styles.read}>
                <p className={styles.questionText}>
                  <span className={styles.questionNumber}>Q{String(index + 1)}</span>{" "}
                  {plainText(question.text)}
                </p>
                {parts[index]?.trim() ? (
                  <p className={styles.written}>{parts[index]}</p>
                ) : (
                  <p className={styles.quiet}>Nothing written.</p>
                )}
              </div>
            ))
          ) : saved.trim() ? (
            <p className={styles.written}>{saved}</p>
          ) : (
            <p className={styles.quiet}>Nothing written.</p>
          )}
          {attachment}
          {transcription !== null && hasTranscription(transcription) ? (
            <TranscriptionPanel transcription={transcription} />
          ) : null}
        </div>
      </Card>
    );
  }

  const submission = joinAnswers(parts, questions);
  const written = parts.some((part) => part.trim() !== "");
  const reading = transcribe.isPending;

  const setPart = (index: number, value: string) => {
    setParts((current) => current.map((part, at) => (at === index ? value : part)));
  };

  const insert = (text: string) => {
    const mark = caret.current;
    const index = Math.min(mark?.index ?? parts.length - 1, parts.length - 1);
    const value = parts[index] ?? "";
    const at =
      mark !== null && mark.index === index ? Math.min(mark.at, value.length) : value.length;
    const before = value.slice(0, at);
    const after = value.slice(at);
    const blank = before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
    const lead = before.trim() === "" ? "" : blank;
    const trail = after.trim() === "" ? "" : "\n\n";
    setPart(index, `${before}${lead}${text}${trail}${after}`);
    setRestore({ index, at: before.length + lead.length + text.length });
  };

  const saveDraft = async () => {
    try {
      await save.mutateAsync({ id: homework.id, submission });
      toast.success("Saved");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const addFile = async (file: File) => {
    try {
      await attach.mutateAsync({ id: homework.id, file });
      toast.success("Attached");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <Card title="Your answers">
      <div className={styles.answers}>
        <div className={styles.boxes} ref={boxes}>
          {questions.length > 0 ? (
            questions.map((question, index) => (
              <AnswerBox
                key={question.id}
                label={`Q${String(index + 1)}`}
                question={plainText(question.text)}
                value={parts[index] ?? ""}
                onChange={(value) => {
                  setPart(index, value);
                }}
                onCaret={(at) => {
                  caret.current = { index, at };
                }}
              />
            ))
          ) : (
            <AnswerBox
              label="Answers"
              question={null}
              value={parts[0] ?? ""}
              onChange={(value) => {
                setPart(0, value);
              }}
              onCaret={(at) => {
                caret.current = { index: 0, at };
              }}
            />
          )}
        </div>

        {attachment ?? (
          // The input clears itself rather than being remounted, so attaching moves
          // neither the focus nor the page.
          <label className={styles.picker}>
            <Camera size={16} aria-hidden="true" />
            Add a photo
            <input
              type="file"
              accept={ACCEPT}
              capture="environment"
              className={styles.pickerInput}
              disabled={attach.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) {
                  void addFile(file);
                }
              }}
            />
          </label>
        )}

        {transcription !== null && hasTranscription(transcription) ? (
          <TranscriptionPanel transcription={transcription} onInsert={insert} />
        ) : null}

        <p className={styles.quiet}>Once handed in, your answers cannot be changed.</p>

        <div className={styles.actions}>
          <Button
            variant="primary"
            disabled={reading || (!written && attachmentId === null)}
            onClick={() => {
              setConfirming(true);
            }}
          >
            Hand in
          </Button>
          <Button
            loading={save.isPending}
            disabled={reading || submission === saved}
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
        message="Your answers cannot be changed afterwards."
        confirmLabel="Hand in"
        cancelLabel="Not yet"
        onConfirm={async () => {
          try {
            await handIn.mutateAsync({ id: homework.id, submission });
          } catch (error) {
            toast.error(apiError(error));
            throw error;
          }
          toast.success("Submitted");
        }}
      />
    </Card>
  );
}
