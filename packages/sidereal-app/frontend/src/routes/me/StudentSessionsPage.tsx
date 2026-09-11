import { formatDayHeading, formatDuration, formatTime } from "@/components/sessions/schedule";
import studentStyles from "@/components/student/student.module.css";
import { EmptyState, Spinner, StatusChip } from "@/components/ui";
import { useMySessions } from "@/lib/queries";
import type { MySession } from "@/lib/queries";

import styles from "./me.module.css";

function SessionRow({ session }: { session: MySession }) {
  return (
    <div className={studentStyles.row}>
      <span className={studentStyles.rowTitle}>
        {formatDayHeading(session.scheduled_at)}, {formatTime(session.scheduled_at)}
      </span>
      <span className={studentStyles.rowMeta}>
        <span>{formatDuration(session.duration_minutes)}</span>
        <StatusChip status={session.status} />
      </span>
    </div>
  );
}

function isUpcoming(session: MySession, now: number): boolean {
  return session.status === "scheduled" && session.scheduled_at !== null && Date.parse(session.scheduled_at) >= now;
}

export function StudentSessionsPage() {
  const { data, isLoading, isError } = useMySessions();

  const now = Date.now();
  const rows = data ?? [];
  const upcoming = rows.filter((session) => isUpcoming(session, now));
  const past = rows.filter((session) => !isUpcoming(session, now)).reverse();

  return (
    <div className={styles.stack}>
      <h1 className={styles.heading}>Lessons</h1>

      {isLoading ? (
        <p className={styles.loading}>
          <Spinner /> Loading your lessons…
        </p>
      ) : null}
      {isError ? <p className={styles.status}>Your lessons could not be loaded. Try again in a moment.</p> : null}

      <section>
        <h2 className={styles.sectionHeading}>Coming up</h2>
        {upcoming.length > 0 ? (
          <ul className={styles.list}>
            {upcoming.map((session) => (
              <li key={session.id}>
                <SessionRow session={session} />
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState message="No lesson booked in yet." />
        )}
      </section>

      {past.length > 0 ? (
        <section>
          <h2 className={styles.sectionHeading}>Earlier</h2>
          <ul className={styles.list}>
            {past.map((session) => (
              <li key={session.id}>
                <SessionRow session={session} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
