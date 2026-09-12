import { useMemo, useState } from "react";

import { SessionCard } from "@/components/sessions/SessionCard";
import { SessionDialog } from "@/components/sessions/SessionDialog";
import { Button, EmptyState, SkeletonRows } from "@/components/ui";
import { useSessionLinks, useSessions } from "@/lib/queries";
import type { SessionListItem } from "@/lib/queries";

import { useStudentTab } from "./context";
import styles from "./SessionsTab.module.css";
import listStyles from "./TabList.module.css";

function isUpcoming(session: SessionListItem, now: number): boolean {
  return session.status === "scheduled" && session.scheduled_at !== null && Date.parse(session.scheduled_at) >= now;
}

export function SessionsTab() {
  const { studentId } = useStudentTab();
  const { data, isLoading, isError } = useSessions({ studentId });
  const links = useSessionLinks(studentId);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<SessionListItem | null>(null);

  const { upcoming, past } = useMemo(() => {
    const now = Date.now();
    const rows = data ?? [];
    return {
      // Soonest first while they are still ahead, most recent first once they are not.
      upcoming: rows.filter((row) => isUpcoming(row, now)).reverse(),
      past: rows.filter((row) => !isUpcoming(row, now)),
    };
  }, [data]);

  const schedule = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const edit = (session: SessionListItem) => {
    setEditing(session);
    setDialogOpen(true);
  };

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <Button variant="primary" onClick={schedule}>
          Schedule a session
        </Button>
      </div>

      {isLoading ? <SkeletonRows count={3} label="Loading sessions" /> : null}
      {isError ? <p className={listStyles.meta}>Could not load sessions.</p> : null}

      {data && data.length === 0 ? (
        <EmptyState
          message="No sessions yet. Schedule the first one and it will show up here."
          action={
            <Button variant="primary" onClick={schedule}>
              Schedule a session
            </Button>
          }
        />
      ) : null}

      {data && data.length > 0 ? (
        <>
          <section className={styles.section}>
            <h2 className={styles.heading}>Upcoming</h2>
            {upcoming.length > 0 ? (
              <div className={styles.list}>
                {upcoming.map((session) => (
                  <SessionCard
                    key={session.id}
                    session={session}
                    links={links.data?.[session.id]}
                    onEdit={edit}
                  />
                ))}
              </div>
            ) : (
              <p className={listStyles.meta}>Nothing scheduled yet.</p>
            )}
          </section>

          <section className={styles.section}>
            <h2 className={styles.heading}>Past</h2>
            {past.length > 0 ? (
              <div className={styles.list}>
                {past.map((session) => (
                  <SessionCard
                    key={session.id}
                    session={session}
                    links={links.data?.[session.id]}
                    onEdit={edit}
                  />
                ))}
              </div>
            ) : (
              <p className={listStyles.meta}>No sessions have happened yet.</p>
            )}
          </section>
        </>
      ) : null}

      <SessionDialog
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
        }}
        studentId={studentId}
        session={editing}
      />
    </div>
  );
}
