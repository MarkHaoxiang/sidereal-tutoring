import { useState } from "react";
import { toast } from "sonner";

import { Button, ConfirmDialog, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useUpdateSession } from "@/lib/queries";
import type { SessionLinkCounts, SessionListItem } from "@/lib/queries";

import { formatDayHeading, formatDuration, formatTime } from "./schedule";
import styles from "./SessionCard.module.css";

/** What is linked to a session, as counts rather than a sentence. */
function linkSummary(links: SessionLinkCounts | undefined): string {
  const parts: string[] = [];
  if (links && links.material > 0) {
    parts.push(`${String(links.material)} material`);
  }
  if (links && links.artefacts > 0) {
    parts.push(`${String(links.artefacts)} work`);
  }
  return parts.join(" · ");
}

export interface SessionCardProps {
  session: SessionListItem;
  links?: SessionLinkCounts;
  onEdit: (session: SessionListItem) => void;
}

export function SessionCard({ session, links, onEdit }: SessionCardProps) {
  const updateSession = useUpdateSession();
  const [confirmCancel, setConfirmCancel] = useState(false);

  const setStatus = async (status: "completed" | "cancelled", message: string) => {
    try {
      await updateSession.mutateAsync({ id: session.id, patch: { status } });
      toast.success(message);
    } catch (error) {
      toast.error(apiError(error));
      throw error;
    }
  };

  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <div>
          <p className={styles.when}>
            {formatDayHeading(session.scheduled_at)}, {formatTime(session.scheduled_at)}
          </p>
          <p className={styles.meta}>
            {[formatDuration(session.duration_minutes), linkSummary(links)].filter(Boolean).join(" · ")}
          </p>
        </div>
        <StatusChip status={session.status} />
      </header>

      {session.notes ? <p className={styles.notes}>{session.notes}</p> : null}

      <footer className={styles.actions}>
        {session.status === "scheduled" ? (
          <Button
            size="sm"
            loading={updateSession.isPending}
            onClick={() => {
              void setStatus("completed", "Completed").catch(() => undefined);
            }}
          >
            Mark completed
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            onEdit(session);
          }}
        >
          Edit
        </Button>
        {session.status === "scheduled" ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setConfirmCancel(true);
            }}
          >
            Cancel session
          </Button>
        ) : null}
      </footer>

      <ConfirmDialog
        open={confirmCancel}
        onClose={() => {
          setConfirmCancel(false);
        }}
        title="Cancel this session?"
        message="It stays in the list, marked as cancelled."
        confirmLabel="Cancel session"
        cancelLabel="Keep it"
        danger
        onConfirm={() => setStatus("cancelled", "Cancelled")}
      />
    </article>
  );
}
