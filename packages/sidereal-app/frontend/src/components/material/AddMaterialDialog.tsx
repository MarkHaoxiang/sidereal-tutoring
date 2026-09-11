import { useState } from "react";
import { toast } from "sonner";

import { Button, Dialog, Field, Input, Select, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import type { DocumentSource } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useCreateDocument, useSessions, useUploadMaterialFile } from "@/lib/queries";

import styles from "./material.module.css";

type Way = "file" | "url" | "text";

const WAYS: { id: Way; label: string }[] = [
  { id: "file", label: "Upload a file" },
  { id: "url", label: "Paste a link" },
  { id: "text", label: "Paste text" },
];

const ACCEPT = ".pdf,.docx,.txt,.vtt,.srt";

export interface AddMaterialDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: string;
}

export function AddMaterialDialog({ open, onClose, studentId }: AddMaterialDialogProps) {
  const sessions = useSessions({ studentId });
  const upload = useUploadMaterialFile();
  const create = useCreateDocument();

  const [way, setWay] = useState<Way>("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [error, setError] = useState<string | null>(null);
  // A file input cannot be cleared by state; remounting it is what empties it.
  const [inputGeneration, setInputGeneration] = useState(0);

  const busy = upload.isPending || create.isPending;

  const close = () => {
    setWay("file");
    setFile(null);
    setUrl("");
    setText("");
    setTitle("");
    setSessionId("");
    setError(null);
    setInputGeneration((generation) => generation + 1);
    onClose();
  };

  const buildSource = async (): Promise<DocumentSource | null> => {
    if (way === "file") {
      if (!file) {
        setError("Choose a file to upload.");
        return null;
      }
      return { type: "file", file_id: await upload.mutateAsync(file) };
    }
    if (way === "url") {
      const link = url.trim();
      if (!link) {
        setError("Paste the link to the page you want to use.");
        return null;
      }
      if (!/^https?:\/\//i.test(link)) {
        setError("A link has to start with http:// or https://");
        return null;
      }
      return { type: "url", url: link };
    }
    if (!text.trim()) {
      setError("Paste the text you want to use.");
      return null;
    }
    return { type: "text", text };
  };

  const save = async () => {
    setError(null);
    try {
      const source = await buildSource();
      if (!source) {
        return;
      }
      await create.mutateAsync({
        student_id: studentId,
        ...(sessionId ? { session_id: sessionId } : {}),
        ...(title.trim() ? { title: title.trim() } : {}),
        source,
      });
      toast.success("Material added — reading it now");
      close();
    } catch (failure) {
      setError(apiError(failure));
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Add material"
      busy={busy}
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={busy}
            onClick={() => {
              void save();
            }}
          >
            Add material
          </Button>
        </>
      }
    >
      <div className={styles.ways}>
        {WAYS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={styles.way}
            aria-pressed={way === option.id}
            onClick={() => {
              setWay(option.id);
              setError(null);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>

      {way === "file" ? (
        <Field
          label="File"
          help="A PDF, Word document, plain text file or a subtitle file from a recording."
          error={error}
        >
          <Input
            key={`file-${String(inputGeneration)}`}
            type="file"
            accept={ACCEPT}
            className={styles.fileInput}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setError(null);
            }}
          />
        </Field>
      ) : null}

      {way === "url" ? (
        <Field label="Link" help="The address of a page you want the material taken from." error={error}>
          <Input
            value={url}
            placeholder="https://"
            onChange={(event) => {
              setUrl(event.target.value);
              setError(null);
            }}
          />
        </Field>
      ) : null}

      {way === "text" ? (
        <>
          <Field label="Name" help="Leave this blank and today's date is used.">
            <Input
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
              }}
            />
          </Field>
          <Field label="Text" error={error}>
            <Textarea
              value={text}
              rows={8}
              placeholder="Paste your notes here."
              onChange={(event) => {
                setText(event.target.value);
                setError(null);
              }}
            />
          </Field>
        </>
      ) : null}

      <Field label="From session" help="Optional — link this material to a lesson.">
        <Select
          value={sessionId}
          onChange={(event) => {
            setSessionId(event.target.value);
          }}
        >
          <option value="">Not from a session</option>
          {(sessions.data ?? []).map((session) => (
            <option key={session.id} value={session.id}>
              {formatDateTime(session.scheduled_at)}
            </option>
          ))}
        </Select>
      </Field>
    </Dialog>
  );
}
