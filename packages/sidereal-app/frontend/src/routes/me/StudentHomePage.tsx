import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { formatDayHeading, formatDuration, formatTime } from "@/components/sessions/schedule";
import { HomeworkRow } from "@/components/student/HomeworkRow";
import { feedbackTitle } from "@/components/student/feedback";
import { byDueDate } from "@/components/student/homework";
import { SkeletonRows } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/format";
import { useMyFeedbackList, useMyHomeworkList, useMyPlans, useMySessions, useMyStudent } from "@/lib/queries";

import styles from "./me.module.css";

interface SectionProps {
  title: string;
  query: { isLoading: boolean; isError: boolean };
  /** The student-voice line for when there is nothing to show. */
  empty: string;
  /** Null when the query came back with nothing, which is what shows `empty`. */
  children: ReactNode;
}

function Section({ title, query, empty, children }: SectionProps) {
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionHeading}>{title}</h2>
      {query.isLoading ? (
        <SkeletonRows count={2} label={`Loading ${title.toLowerCase()}`} />
      ) : query.isError ? (
        <p className={styles.status}>Could not load this.</p>
      ) : (
        (children ?? <p className={styles.quiet}>{empty}</p>)
      )}
    </section>
  );
}

export function StudentHomePage() {
  const { me } = useAuth();
  const student = useMyStudent();
  const homework = useMyHomeworkList();
  const feedback = useMyFeedbackList();
  const plans = useMyPlans();
  const sessions = useMySessions();

  const greetingName = me?.first_name ?? student.data?.name ?? null;
  const due = (homework.data ?? []).filter((row) => row.status === "assigned").sort(byDueDate);
  const recentFeedback = (feedback.data ?? []).slice(0, 3);
  const activePlan = (plans.data ?? []).find((plan) => plan.status === "active");
  const now = Date.now();
  const nextSession = (sessions.data ?? []).find(
    (session) =>
      session.status === "scheduled" && session.scheduled_at !== null && Date.parse(session.scheduled_at) >= now
  );

  return (
    <div className={styles.stack}>
      <header className={styles.note}>
        <h1 className={styles.greeting}>{greetingName ? `Hello, ${greetingName}` : "Hello"}</h1>
      </header>

      <Section title="Due soon" query={homework} empty="Nothing due right now — nice.">
        {due.length > 0 ? (
          <ul className={styles.list}>
            {due.map((row) => (
              <li key={row.id}>
                <HomeworkRow homework={row} />
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="New feedback" query={feedback} empty="Nothing yet — feedback turns up after a lesson.">
        {recentFeedback.length > 0 ? (
          <ul className={styles.list}>
            {recentFeedback.map((row) => (
              <li key={row.id} className={styles.feedbackRow}>
                <Link to={`/me/feedback/${row.id}`} className={styles.feedbackLink}>
                  {feedbackTitle(row.content)}
                </Link>
                <span className={styles.status}>{formatDate(row.date_created)}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </Section>

      <Section title="Your next lesson" query={sessions} empty="No lesson booked in yet.">
        {nextSession ? (
          <p className={styles.line}>
            <span className={styles.strong}>
              {formatDayHeading(nextSession.scheduled_at)}, {formatTime(nextSession.scheduled_at)}
            </span>
            {` · ${formatDuration(nextSession.duration_minutes)}`}
          </p>
        ) : null}
      </Section>

      <Section
        title="Your study plan"
        query={plans}
        empty="No study plan yet."
      >
        {activePlan ? (
          <p className={styles.line}>
            <Link to="/me/plan" className={styles.feedbackLink}>
              {activePlan.title ?? "Your study plan"}
            </Link>
          </p>
        ) : null}
      </Section>
    </div>
  );
}
