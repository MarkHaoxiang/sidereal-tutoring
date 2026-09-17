import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button, Dialog, Field, Input, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useCreateSession, useUpdateSession } from "@/lib/queries";
import type { SessionListItem } from "@/lib/queries";

import { fromDateTimeInputs, toDateTimeInputs } from "./schedule";

const DEFAULT_DURATION = "60";

interface Draft {
  date: string;
  time: string;
  duration: string;
  notes: string;
}

function toDraft(session: SessionListItem | null | undefined): Draft {
  const { date, time } = toDateTimeInputs(session?.scheduled_at ?? null);
  return {
    date,
    time,
    duration: session?.duration_minutes ? String(session.duration_minutes) : DEFAULT_DURATION,
    notes: session?.notes ?? "",
  };
}

export interface SessionDialogProps {
  open: boolean;
  onClose: () => void;
  studentId: string;
  /** Omit to schedule a new session; pass one to change it. */
  session?: SessionListItem | null;
}

export function SessionDialog({ open, onClose, studentId, session }: SessionDialogProps) {
  const createSession = useCreateSession();
  const updateSession = useUpdateSession();
  const [draft, setDraft] = useState<Draft>(() => toDraft(session));
  const [dateError, setDateError] = useState<string | null>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open && !wasOpen.current) {
      setDraft(toDraft(session));
      setDateError(null);
    }
    wasOpen.current = open;
  }, [open, session]);

  const pending = createSession.isPending || updateSession.isPending;

  const save = async () => {
    const scheduledAt = fromDateTimeInputs(draft.date, draft.time);
    if (!scheduledAt) {
      setDateError("Pick the day the session happens on.");
      return;
    }
    const duration = Number.parseInt(draft.duration, 10);
    const values = {
      scheduled_at: scheduledAt,
      duration_minutes: Number.isNaN(duration) || duration <= 0 ? null : duration,
      notes: draft.notes.trim() || null,
    };
    try {
      if (session) {
        await updateSession.mutateAsync({ id: session.id, patch: values });
        toast.success("Saved");
      } else {
        await createSession.mutateAsync({ ...values, student: studentId, status: "scheduled" });
        toast.success("Scheduled");
      }
      onClose();
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={session ? "Change this session" : "Schedule a session"}
      busy={pending}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={pending}
            onClick={() => {
              void save();
            }}
          >
            {session ? "Save changes" : "Schedule session"}
          </Button>
        </>
      }
    >
      <Field label="Date" required error={dateError}>
        <Input
          type="date"
          value={draft.date}
          autoFocus
          onChange={(event) => {
            setDraft((current) => ({ ...current, date: event.target.value }));
            setDateError(null);
          }}
        />
      </Field>
      <Field label="Start time" required>
        <Input
          type="time"
          value={draft.time}
          onChange={(event) => {
            setDraft((current) => ({ ...current, time: event.target.value }));
          }}
        />
      </Field>
      <Field label="Length in minutes">
        <Input
          type="number"
          min={5}
          step={5}
          value={draft.duration}
          onChange={(event) => {
            setDraft((current) => ({ ...current, duration: event.target.value }));
          }}
        />
      </Field>
      <Field label="Notes">
        <Textarea
          value={draft.notes}
          onChange={(event) => {
            setDraft((current) => ({ ...current, notes: event.target.value }));
          }}
        />
      </Field>
    </Dialog>
  );
}
