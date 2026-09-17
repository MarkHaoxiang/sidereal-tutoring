import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { structureQuestions } from "@/components/papers/draft";
import { TopicPicker } from "@/components/topics/TopicPicker";
import { Button, Dialog, Field, Input, Select, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import type { DocumentSource } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import {
  useCreateDocument,
  usePapers,
  useSessions,
  useTagDocument,
  useUploadMaterialFile,
  useUploadScanPages,
} from "@/lib/queries";

import styles from "./material.module.css";

type Way = "file" | "url" | "text" | "scan";

const WAYS: { id: Way; label: string }[] = [
  { id: "file", label: "Upload a file" },
  { id: "url", label: "Paste a link" },
  { id: "text", label: "Paste text" },
  { id: "scan", label: "Scan handwriting" },
];

const ACCEPT = ".pdf,.docx,.txt,.vtt,.srt";
const SCAN_ACCEPT = ".jpg,.jpeg,.png,.webp,.heic,.heif,.pdf";

const isPdf = (file: File) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

export interface AddMaterialDialogProps {
  open: boolean;
  onClose: () => void;
  /** Left out for the library: material every tutor can use belongs to no student. */
  studentId?: string;
}

/** Its own component so the student's lessons are only fetched when there is a student. */
function SessionField({
  studentId,
  value,
  onChange,
}: {
  studentId: string;
  value: string;
  onChange: (next: string) => void;
}) {
  const sessions = useSessions({ studentId });
  return (
    <Field label="From session (optional)">
      <Select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
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
  );
}

/** Its own component so the library's papers are only fetched when a scan is being added. */
function PaperField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const papers = usePapers();
  // A paper with no questions yet cannot be matched against, so it is not offered.
  const usable = (papers.data ?? []).filter((paper) => structureQuestions(paper.structure).length > 0);
  return (
    <Field label="Solutions to (optional)">
      <Select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        <option value="">Notes, not a paper</option>
        {usable.map((paper) => (
          <option key={paper.id} value={paper.id}>
            {paper.title}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function AddMaterialDialog({ open, onClose, studentId }: AddMaterialDialogProps) {
  const upload = useUploadMaterialFile();
  const uploadPages = useUploadScanPages();
  const create = useCreateDocument();
  const tag = useTagDocument();

  const [way, setWay] = useState<Way>("file");
  const [file, setFile] = useState<File | null>(null);
  const [pages, setPages] = useState<File[]>([]);
  const [paperId, setPaperId] = useState("");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [topics, setTopics] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  // A file input cannot be cleared by state; remounting it is what empties it.
  const [inputGeneration, setInputGeneration] = useState(0);

  const busy = upload.isPending || uploadPages.isPending || create.isPending || tag.isPending;

  // The chosen photos as they are, before anything is uploaded; a PDF shows its name.
  const previews = useMemo(
    () =>
      pages
        .filter((page) => !isPdf(page))
        .map((page) => ({ name: page.name, url: URL.createObjectURL(page) })),
    [pages]
  );

  useEffect(
    () => () => {
      for (const preview of previews) {
        URL.revokeObjectURL(preview.url);
      }
    },
    [previews]
  );

  const close = () => {
    setWay("file");
    setFile(null);
    setPages([]);
    setPaperId("");
    setUrl("");
    setText("");
    setTitle("");
    setSessionId("");
    setTopics([]);
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
    if (way === "scan") {
      if (pages.length === 0) {
        setError("Choose the pages to scan.");
        return null;
      }
      if (pages.some(isPdf) && pages.length > 1) {
        setError("Choose photos, or one PDF.");
        return null;
      }
      return {
        type: "scan",
        file_ids: await uploadPages.mutateAsync(pages),
        ...(paperId ? { paper_id: paperId } : {}),
      };
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
      const document = await create.mutateAsync({
        ...(studentId ? { student_id: studentId } : {}),
        ...(sessionId ? { session_id: sessionId } : {}),
        ...(title.trim() ? { title: title.trim() } : {}),
        source,
      });
      if (topics.length > 0) {
        await tag.mutateAsync({ id: document.id, topics });
      }
      toast.success("Added — reading it now");
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
        <Field label="File" help="PDF, Word, text or subtitles." error={error}>
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

      {way === "scan" ? (
        <>
          <Field label="Pages" help="Photos in order, or one PDF." error={error}>
            <Input
              key={`pages-${String(inputGeneration)}`}
              type="file"
              accept={SCAN_ACCEPT}
              multiple
              className={styles.fileInput}
              onChange={(event) => {
                setPages([...(event.target.files ?? [])]);
                setError(null);
              }}
            />
          </Field>
          {previews.length > 0 ? (
            <ul className={styles.picks}>
              {previews.map((preview, index) => (
                <li key={preview.url} className={styles.pick}>
                  <img src={preview.url} alt={preview.name} className={styles.pickImage} />
                  <span className={styles.pickIndex}>{index + 1}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {pages.some(isPdf) ? <p className={styles.pickPdf}>{pages[0]?.name}</p> : null}
          <PaperField value={paperId} onChange={setPaperId} />
        </>
      ) : null}

      {way === "url" ? (
        <Field label="Link" error={error}>
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
          <Field label="Name" help="Blank uses today's date.">
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

      <Field label="Topics (optional)">
        <TopicPicker value={topics} onChange={setTopics} disabled={busy} />
      </Field>

      {studentId ? (
        <SessionField studentId={studentId} value={sessionId} onChange={setSessionId} />
      ) : null}
    </Dialog>
  );
}
