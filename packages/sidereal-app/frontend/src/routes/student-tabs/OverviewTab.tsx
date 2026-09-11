import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { formatDayHeading, formatTime } from "@/components/sessions/schedule";
import { artefactPath, collectArtefacts } from "@/components/students/artefacts";
import { Button, Card, EmptyState, Spinner, StatusChip, Textarea } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import {
  useFeedbackList,
  useHomeworkList,
  usePlans,
  useSessions,
  useStudent,
  useUpdateStudent,
} from "@/lib/queries";

import { useStudentTab } from "./context";
import styles from "./OverviewTab.module.css";
import listStyles from "./TabList.module.css";

export function OverviewTab() {
  const { studentId } = useStudentTab();
  const navigate = useNavigate();
  const student = useStudent(studentId);
  const updateStudent = useUpdateStudent();

  const now = useMemo(() => new Date().toISOString(), []);
  const upcoming = useSessions({
    studentId,
    status: "scheduled",
    from: now,
    sort: "scheduled_at",
    limit: 1,
  });
  const homework = useHomeworkList({ studentId, limit: 3 });
  const feedback = useFeedbackList({ studentId, limit: 3 });
  const plans = usePlans({ studentId, limit: 3 });

  // `null` means "not edited" — the saved notes are what shows until the tutor types.
  const [draftNotes, setDraftNotes] = useState<string | null>(null);
  const savedNotes = student.data?.notes ?? "";
  const notes = draftNotes ?? savedNotes;
  const isDirty = draftNotes !== null && draftNotes !== savedNotes;

  const recent = collectArtefacts({
    homework: homework.data,
    feedback: feedback.data,
    plans: plans.data,
  }).slice(0, 3);

  const saveNotes = async () => {
    try {
      await updateStudent.mutateAsync({ id: studentId, patch: { notes: notes.trim() || null } });
      setDraftNotes(null);
      toast.success("Notes saved");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  if (student.isLoading) {
    return (
      <p className={listStyles.meta}>
        <Spinner /> Loading…
      </p>
    );
  }

  const nextSession = upcoming.data?.[0];

  return (
    <div className={styles.panel}>
      <Card title="Notes">
        <div className={styles.notes}>
          <Textarea
            value={notes}
            rows={5}
            aria-label="Notes about this student"
            placeholder="Anything worth remembering — how they learn, what they are working towards, exam dates."
            onChange={(event) => {
              setDraftNotes(event.target.value);
            }}
          />
          <div className={styles.notesActions}>
            {isDirty ? <span className={listStyles.meta}>Unsaved changes</span> : null}
            <Button
              variant="secondary"
              disabled={!isDirty}
              loading={updateStudent.isPending}
              onClick={() => {
                void saveNotes();
              }}
            >
              Save notes
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Next session">
        {nextSession ? (
          <p className={styles.next}>
            <span className={styles.nextWhen}>
              {formatDayHeading(nextSession.scheduled_at)}, {formatTime(nextSession.scheduled_at)}
            </span>
            <Link to={`/students/${studentId}/sessions`}>All sessions</Link>
          </p>
        ) : (
          <EmptyState
            message="No session scheduled."
            action={
              <Button
                variant="primary"
                onClick={() => {
                  void navigate(`/students/${studentId}/sessions`);
                }}
              >
                Schedule a session
              </Button>
            }
          />
        )}
      </Card>

      <Card title="Latest work">
        {recent.length > 0 ? (
          <ul className={styles.list}>
            {recent.map((artefact) => (
              <li key={`${artefact.kind}-${artefact.id}`} className={styles.row}>
                <Link to={artefactPath(studentId, artefact.kind, artefact.id)}>{artefact.title}</Link>
                <span className={styles.rowMeta}>
                  <StatusChip status={artefact.kind} />
                  <StatusChip status={artefact.status} />
                  <span className={listStyles.meta}>{formatDateTime(artefact.created)}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState message="Nothing generated for this student yet. Add material first, then generate homework, feedback or a study plan." />
        )}
      </Card>
    </div>
  );
}
