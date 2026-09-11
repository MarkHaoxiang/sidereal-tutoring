import { useEffect, useState } from "react";

import { Button, Dialog, Field, Input, Spinner, StatusChip, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { useCreateJob, useDocuments, useSessions } from "@/lib/queries";
import type { DocumentListItem } from "@/lib/queries";
import type { GenerationJobKind } from "@/lib/schema";

import { ARTEFACT_KINDS } from "./kinds";
import styles from "./artefacts.module.css";

export interface GenerateDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: string;
  kind: GenerationJobKind;
  /** Handed the queued job's id; the caller shows the progress. */
  onStarted: (jobId: string) => void;
}

function sessionIdOf(document: DocumentListItem): string | null {
  return typeof document.session === "string" ? document.session : (document.session?.id ?? null);
}

export function GenerateDialog({ open, onClose, studentId, kind, onStarted }: GenerateDialogProps) {
  const copy = ARTEFACT_KINDS[kind];
  const documents = useDocuments({ studentId, status: ["ready"] });
  const lastLesson = useSessions({
    studentId,
    status: "completed",
    sort: "-scheduled_at",
    limit: 1,
  });
  const createJob = useCreateJob();

  const [selected, setSelected] = useState<string[]>([]);
  const [instructions, setInstructions] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [primed, setPrimed] = useState(false);

  const ready = documents.data;
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
    setInstructions("");
    setPeriodStart("");
    setPeriodEnd("");
    setError(null);
    onClose();
  };

  const toggle = (id: string) => {
    setError(null);
    setSelected((current) => (current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]));
  };

  const submit = async () => {
    if (selected.length === 0) {
      setError("Choose at least one piece of material to work from.");
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
        instructions: instructions.trim() || null,
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
            disabled={!ready || ready.length === 0}
            onClick={() => {
              void submit();
            }}
          >
            {copy.generateLabel}
          </Button>
        </>
      }
    >
      <Field
        label="Material to work from"
        help={lastLessonId ? "Material from the last lesson is ticked for you." : undefined}
        error={error}
      >
        {documents.isLoading ? (
          <p className={styles.status}>
            <Spinner /> Loading material…
          </p>
        ) : null}
        {ready && ready.length === 0 ? (
          <p className={styles.status}>
            Nothing to work from yet. Add material on the Material tab and wait until it says Ready.
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

      <Field label="Instructions" help="Optional — anything you would tell a colleague doing this for you.">
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
