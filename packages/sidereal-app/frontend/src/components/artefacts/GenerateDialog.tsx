import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { libraryTopics, matchesLibraryFilter } from "@/components/material/library";
import { TopicFilter } from "@/components/topics/TopicFilter";
import { Button, Dialog, Field, Input, Spinner, StatusChip, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import {
  useCreateJob,
  useDocuments,
  useHomeworkList,
  useLibraryDocuments,
  useSessions,
} from "@/lib/queries";
import type { DocumentListItem } from "@/lib/queries";
import type { HomeworkFormat } from "@/lib/schema";

import { ARTEFACT_KINDS } from "./kinds";
import type { ArtefactKind } from "./kinds";
import styles from "./artefacts.module.css";

export interface GenerateDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: string;
  kind: ArtefactKind;
  /** Handed the queued job's id; the caller shows the progress. */
  onStarted: (jobId: string) => void;
}

const FORMATS: { id: HomeworkFormat; label: string }[] = [
  { id: "markdown", label: "Written (markdown)" },
  { id: "typst", label: "Typeset (PDF)" },
];

function sessionIdOf(document: DocumentListItem): string | null {
  return typeof document.session === "string" ? document.session : (document.session?.id ?? null);
}

export function GenerateDialog({ open, onClose, studentId, kind, onStarted }: GenerateDialogProps) {
  const copy = ARTEFACT_KINDS[kind];
  const documents = useDocuments({ studentId, status: ["ready"] });
  const library = useLibraryDocuments({ status: ["ready"] });
  const lastLesson = useSessions({
    studentId,
    status: "completed",
    sort: "-scheduled_at",
    limit: 1,
  });
  // Feedback is about what the student handed in, so those rows are offered to it alone.
  const handIns = useHomeworkList({ studentId, status: ["submitted", "marked"] }, open && copy.hasHomework);
  const createJob = useCreateJob();

  const [selected, setSelected] = useState<string[]>([]);
  const [homework, setHomework] = useState<string[]>([]);
  const [instructions, setInstructions] = useState("");
  const [format, setFormat] = useState<HomeworkFormat>("markdown");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [primed, setPrimed] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [librarySearch, setLibrarySearch] = useState("");
  const [libraryTopic, setLibraryTopic] = useState<string | null>(null);

  const ready = documents.data;
  const shared = useMemo(() => library.data ?? [], [library.data]);
  const sharedTopics = useMemo(() => libraryTopics(shared), [shared]);
  const sharedVisible = shared.filter((row) =>
    matchesLibraryFilter(row, { search: librarySearch, topic: libraryTopic })
  );
  const sharedChosen = shared.filter((row) => selected.includes(row.id)).length;
  const lastLessonId = lastLesson.data?.[0]?.id;
  const periodError =
    periodStart && periodEnd && periodEnd < periodStart
      ? `End the plan on or after ${formatDate(periodStart)}.`
      : null;

  // Opening the dialog ticks the material from the last lesson; after that the tutor's
  // choices stand, however the queries refetch underneath.
  useEffect(() => {
    if (!open) {
      setPrimed(false);
      return;
    }
    if (primed || !ready || lastLesson.isLoading) {
      return;
    }
    setSelected(lastLessonId ? ready.filter((row) => sessionIdOf(row) === lastLessonId).map((row) => row.id) : []);
    setPrimed(true);
  }, [open, primed, ready, lastLesson.isLoading, lastLessonId]);

  const close = () => {
    setSelected([]);
    setHomework([]);
    setInstructions("");
    setFormat("markdown");
    setPeriodStart("");
    setPeriodEnd("");
    setError(null);
    setLibraryOpen(false);
    setLibrarySearch("");
    setLibraryTopic(null);
    onClose();
  };

  const toggle = (id: string) => {
    setError(null);
    setSelected((current) => (current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]));
  };

  const toggleHomework = (id: string) => {
    setError(null);
    setHomework((current) => (current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]));
  };

  const submit = async () => {
    if (selected.length === 0 && homework.length === 0) {
      setError(
        copy.hasHomework
          ? "Choose the homework this is about, or some material to work from."
          : "Choose at least one piece of material to work from."
      );
      return;
    }
    if (periodError) {
      return;
    }
    try {
      const job = await createJob.mutateAsync({
        kind,
        student_id: studentId,
        document_ids: selected,
        ...(copy.hasHomework ? { homework_ids: homework } : {}),
        instructions: instructions.trim() || null,
        format: copy.hasFormat ? format : "markdown",
        ...(copy.hasPeriod ? { period_start: periodStart || null, period_end: periodEnd || null } : {}),
      });
      onStarted(job.id);
      close();
    } catch (failure) {
      setError(apiError(failure));
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title={copy.generateLabel}
      busy={createJob.isPending}
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={createJob.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={createJob.isPending}
            disabled={!ready || (ready.length === 0 && shared.length === 0)}
            onClick={() => {
              void submit();
            }}
          >
            {copy.generateLabel}
          </Button>
        </>
      }
    >
      {copy.hasHomework ? (
        <Field label="About this homework" help="Its questions, what was handed in, and the marks.">
          {handIns.isLoading ? (
            <p className={styles.status}>
              <Spinner /> Loading homework…
            </p>
          ) : null}
          {handIns.data && handIns.data.length === 0 ? (
            <p className={styles.status}>Nothing handed in yet.</p>
          ) : null}
          {handIns.data && handIns.data.length > 0 ? (
            <div className={styles.material}>
              {handIns.data.map((row) => (
                <label key={row.id} className={styles.choice}>
                  <input
                    type="checkbox"
                    checked={homework.includes(row.id)}
                    onChange={() => {
                      toggleHomework(row.id);
                    }}
                  />
                  <span className={styles.choiceTitle}>{row.title ?? "Untitled homework"}</span>
                  <StatusChip status={row.status} />
                  <span className={styles.choiceDate}>{formatDateTime(row.date_created)}</span>
                </label>
              ))}
            </div>
          ) : null}
        </Field>
      ) : null}

      <Field
        label="Material to work from"
        help={lastLessonId ? "The last lesson's material is ticked." : undefined}
        error={error}
      >
        {documents.isLoading ? (
          <p className={styles.status}>
            <Spinner /> Loading material…
          </p>
        ) : null}
        {ready && ready.length === 0 ? (
          <p className={styles.status}>
            {shared.length > 0
              ? "Nothing for this student yet — choose from the library below."
              : "Nothing to work from yet. Add material on the Material tab."}
          </p>
        ) : null}
        {ready && ready.length > 0 ? (
          <div className={styles.material}>
            {ready.map((row) => (
              <label key={row.id} className={styles.choice}>
                <input
                  type="checkbox"
                  checked={selected.includes(row.id)}
                  onChange={() => {
                    toggle(row.id);
                  }}
                />
                <span className={styles.choiceTitle}>{row.title ?? "Untitled material"}</span>
                <StatusChip status={row.kind} />
                <span className={styles.choiceDate}>{formatDateTime(row.date_created)}</span>
              </label>
            ))}
          </div>
        ) : null}
      </Field>

      <div className={styles.library}>
        <button
          type="button"
          className={styles.libraryToggle}
          aria-expanded={libraryOpen}
          onClick={() => {
            setLibraryOpen((open) => !open);
          }}
        >
          {libraryOpen ? (
            <ChevronDown size={14} aria-hidden="true" />
          ) : (
            <ChevronRight size={14} aria-hidden="true" />
          )}
          From the library
          <span className={styles.libraryCount}>
            {library.isLoading ? "…" : shared.length}
            {sharedChosen > 0 ? ` · ${String(sharedChosen)} chosen` : ""}
          </span>
        </button>

        {libraryOpen ? (
          <div className={styles.libraryBody}>
            {shared.length > 0 ? (
              <>
                <Input
                  type="search"
                  value={librarySearch}
                  placeholder="Search the library"
                  aria-label="Search the library by name"
                  onChange={(event) => {
                    setLibrarySearch(event.target.value);
                  }}
                />
                <TopicFilter topics={sharedTopics} value={libraryTopic} onChange={setLibraryTopic} />
              </>
            ) : null}
            {library.isLoading ? (
              <p className={styles.status}>
                <Spinner /> Loading the library…
              </p>
            ) : null}
            {library.data && shared.length === 0 ? (
              <p className={styles.status}>The library is empty.</p>
            ) : null}
            {shared.length > 0 && sharedVisible.length === 0 ? (
              <p className={styles.status}>Nothing matches.</p>
            ) : null}
            {sharedVisible.length > 0 ? (
              <div className={styles.material}>
                {sharedVisible.map((row) => (
                  <label key={row.id} className={styles.choice}>
                    <input
                      type="checkbox"
                      checked={selected.includes(row.id)}
                      onChange={() => {
                        toggle(row.id);
                      }}
                    />
                    <span className={styles.choiceTitle}>{row.title ?? "Untitled material"}</span>
                    <StatusChip status={row.kind} />
                    <span className={styles.choiceDate}>{formatDateTime(row.date_created)}</span>
                  </label>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {copy.hasFormat ? (
        <Field label="Format">
          <div className={styles.formats}>
            {FORMATS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={styles.format}
                aria-pressed={format === option.id}
                onClick={() => {
                  setFormat(option.id);
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        </Field>
      ) : null}

      <Field label="Instructions (optional)">
        <Textarea
          value={instructions}
          rows={4}
          placeholder={copy.instructionsPlaceholder}
          onChange={(event) => {
            setInstructions(event.target.value);
          }}
        />
      </Field>

      {copy.hasPeriod ? (
        <div className={styles.dates}>
          <Field label="Plan starts">
            <Input
              type="date"
              value={periodStart}
              onChange={(event) => {
                setPeriodStart(event.target.value);
              }}
            />
          </Field>
          <Field label="Plan ends" error={periodError}>
            <Input
              type="date"
              value={periodEnd}
              onChange={(event) => {
                setPeriodEnd(event.target.value);
              }}
            />
          </Field>
        </div>
      ) : null}
    </Dialog>
  );
}
