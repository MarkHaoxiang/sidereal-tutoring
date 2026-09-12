import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { dayKey, formatDayHeading, formatTime } from "@/components/sessions/schedule";
import { artefactPath, collectArtefacts } from "@/components/students/artefacts";
import { Button, Card, EmptyState, PageHeader, SkeletonRows, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import {
  useDocuments,
  useFeedbackList,
  useHomeworkList,
  usePlans,
  useRetryDocument,
  useSessions,
  useStudents,
} from "@/lib/queries";
import type { SessionListItem } from "@/lib/queries";

import styles from "./HomePage.module.css";
import pageStyles from "./page.module.css";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function groupByDay(sessions: SessionListItem[]): { key: string; heading: string; rows: SessionListItem[] }[] {
  const days: { key: string; heading: string; rows: SessionListItem[] }[] = [];
  for (const session of sessions) {
    const key = dayKey(session.scheduled_at);
    const last = days.length > 0 ? days[days.length - 1] : undefined;
    if (last && last.key === key) {
      last.rows.push(session);
    } else {
      days.push({ key, heading: formatDayHeading(session.scheduled_at), rows: [session] });
    }
  }
  return days;
}

export function HomePage() {
  const navigate = useNavigate();
  const { from, to } = useMemo(() => {
    const now = new Date();
    return { from: now.toISOString(), to: new Date(now.getTime() + WEEK_MS).toISOString() };
  }, []);

  const students = useStudents({ status: "active" });
  const sessions = useSessions({ status: "scheduled", from, to, sort: "scheduled_at" });
  // Handed-in homework is a review too, so it sits beside the drafts.
  const homework = useHomeworkList({ status: ["draft", "submitted"], limit: 10 });
  const feedback = useFeedbackList({ status: ["draft"], limit: 10 });
  const plans = usePlans({ status: ["draft"], limit: 10 });
  const material = useDocuments({ status: ["pending", "processing", "failed"], limit: 20 });
  const retryDocument = useRetryDocument();

  const days = groupByDay(sessions.data ?? []);
  const waiting = collectArtefacts({
    homework: homework.data,
    feedback: feedback.data,
    plans: plans.data,
  });
  const hasStudents = (students.data ?? []).length > 0;

  const retry = async (id: string, title: string) => {
    try {
      await retryDocument.mutateAsync(id);
      toast.success(`Reading ${title} again`);
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <div className={pageStyles.stack}>
      <PageHeader
        eyebrow="Your week"
        title="Home"
        subtitle="What is coming up, what is waiting on you, and what is still being read."
      />

      <Card title="Upcoming sessions">
        {sessions.isLoading ? (
          <SkeletonRows count={3} variant="line" label="Loading your upcoming sessions" />
        ) : days.length > 0 ? (
          <div className={styles.days}>
            {days.map((day) => (
              <section key={day.key} className={styles.day}>
                <h3 className={styles.dayHeading}>{day.heading}</h3>
                <ul className={styles.list}>
                  {day.rows.map((session) => (
                    <li key={session.id} className={styles.row}>
                      <span className={styles.time}>{formatTime(session.scheduled_at)}</span>
                      {session.student ? (
                        <Link to={`/students/${session.student.id}/sessions`}>{session.student.name}</Link>
                      ) : (
                        <span>Session</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        ) : (
          <EmptyState
            message={
              hasStudents
                ? "Nothing in the diary for the next seven days."
                : "No students yet. Add your first student to start planning lessons."
            }
            action={
              <Button
                variant="primary"
                onClick={() => {
                  void navigate("/students");
                }}
              >
                {hasStudents ? "Go to students" : "Add your first student"}
              </Button>
            }
          />
        )}
      </Card>

      <Card title="Waiting for your review">
        {homework.isLoading || feedback.isLoading || plans.isLoading ? (
          <SkeletonRows count={2} variant="line" label="Loading what is waiting for your review" />
        ) : waiting.length > 0 ? (
          <ul className={styles.list}>
            {waiting.map((artefact) => (
              <li key={`${artefact.kind}-${artefact.id}`} className={styles.row}>
                {artefact.student ? (
                  <Link to={artefactPath(artefact.student.id, artefact.kind, artefact.id)}>
                    {artefact.title}
                  </Link>
                ) : (
                  <span>{artefact.title}</span>
                )}
                <span className={styles.rowMeta}>
                  <StatusChip status={artefact.kind} />
                  {artefact.status === "submitted" ? (
                    <span className={styles.note}>handed in</span>
                  ) : null}
                  {artefact.student ? <span>{artefact.student.name}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState message="Nothing is waiting for you — the desk is clear." />
        )}
      </Card>

      <Card title="Material">
        {material.isLoading ? (
          <SkeletonRows count={2} variant="line" label="Loading material" />
        ) : material.data && material.data.length > 0 ? (
          <ul className={styles.list}>
            {material.data.map((document) => {
              const title = document.title ?? "Untitled material";
              return (
                <li key={document.id} className={styles.materialRow}>
                  <span className={styles.rowMeta}>
                    {document.student ? (
                      <Link to={`/students/${document.student.id}/material/${document.id}`}>{title}</Link>
                    ) : (
                      <span>{title}</span>
                    )}
                    <StatusChip status={document.status} />
                    {document.student ? (
                      <span className={pageStyles.status}>{document.student.name}</span>
                    ) : null}
                  </span>
                  {document.status === "failed" ? (
                    <span className={styles.rowMeta}>
                      {document.error ? <span className={styles.error}>{document.error}</span> : null}
                      <Button
                        size="sm"
                        loading={retryDocument.isPending && retryDocument.variables === document.id}
                        onClick={() => {
                          void retry(document.id, title);
                        }}
                      >
                        Try again
                      </Button>
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState message="Every piece of material has been read and is ready to use." />
        )}
      </Card>
    </div>
  );
}
