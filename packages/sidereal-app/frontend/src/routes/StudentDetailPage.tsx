import { useId, useMemo, useState } from "react";
import { Outlet, useParams } from "react-router-dom";
import { toast } from "sonner";

import { StudentDialog } from "@/components/students/StudentDialog";
import { StudentLogin } from "@/components/students/StudentLogin";
import { Button, ConfirmDialog, PageHeader, Select, Spinner, StatusChip, TabPanel, Tabs } from "@/components/ui";
import { apiError } from "@/lib/api";
import { callerRole, useAuth } from "@/lib/auth-context";
import {
  relationId,
  tutorName,
  useReassignStudent,
  useStudent,
  useStudentLogin,
  useTutorUsers,
  useUpdateStudent,
} from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./StudentDetailPage.module.css";

const PANEL_ID = "student-sections";

export function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: student, isLoading, isError } = useStudent(id);
  const updateStudent = useUpdateStudent();
  // `user` comes back as an id; its email is a `directus_users` read of its own.
  const loginUserId = typeof student?.user === "string" ? student.user : null;
  const login = useStudentLogin(loginUserId);
  const [editOpen, setEditOpen] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  // Whose student this is, is the admin's to change: `students.tutor` is what every
  // tutor-side row filter hangs off.
  const { me } = useAuth();
  const isAdmin = callerRole(me) === "admin";
  const tutorUsers = useTutorUsers(isAdmin);
  const reassign = useReassignStudent();
  const currentTutor = relationId(student?.tutor) ?? "";
  const reassignId = useId();

  const tabs = useMemo(
    () => [
      { to: `/students/${id ?? ""}/overview`, label: "Overview" },
      { to: `/students/${id ?? ""}/sessions`, label: "Sessions" },
      { to: `/students/${id ?? ""}/material`, label: "Material" },
      { to: `/students/${id ?? ""}/homework`, label: "Homework" },
      { to: `/students/${id ?? ""}/feedback`, label: "Feedback" },
      { to: `/students/${id ?? ""}/plans`, label: "Plans" },
    ],
    [id]
  );

  if (!id) {
    return <p className={pageStyles.status}>No student selected.</p>;
  }

  const isArchived = student?.status === "archived";

  const handOver = async (tutor: string | null) => {
    try {
      await reassign.mutateAsync({ id, tutor });
      toast.success(tutor ? "Tutor changed" : "Tutor removed");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  const toggleArchive = async () => {
    try {
      await updateStudent.mutateAsync({ id, patch: { status: isArchived ? "active" : "archived" } });
      toast.success(isArchived ? "Unarchived" : "Archived");
    } catch (error) {
      toast.error(apiError(error));
      throw error;
    }
  };

  return (
    <div>
      {isLoading ? (
        <p className={pageStyles.loading}>
          <Spinner /> Loading student…
        </p>
      ) : null}
      {isError ? <p className={pageStyles.status}>Could not load this student.</p> : null}

      {student ? (
        <PageHeader
          back={{ to: "/students", label: "Students" }}
          title={student.name}
          actions={
            <>
              <Button
                onClick={() => {
                  setEditOpen(true);
                }}
              >
                Edit
              </Button>
              <Button
                variant={isArchived ? "secondary" : "ghost"}
                onClick={() => {
                  setConfirmArchive(true);
                }}
              >
                {isArchived ? "Unarchive" : "Archive"}
              </Button>
            </>
          }
          meta={
            <>
              <StatusChip status={student.status} />
              {student.level ? <span>{student.level}</span> : null}
              {(student.subjects ?? []).map((subject) => (
                <span key={subject} className={styles.subject}>
                  {subject}
                </span>
              ))}
              {isAdmin ? (
                <span className={styles.reassign}>
                  <label htmlFor={reassignId}>Tutor</label>
                  <Select
                    id={reassignId}
                    className={styles.reassignSelect}
                    value={currentTutor}
                    disabled={reassign.isPending}
                    onChange={(event) => {
                      void handOver(event.target.value || null);
                    }}
                  >
                    <option value="">Nobody</option>
                    {(tutorUsers.data ?? []).map((tutor) => (
                      <option key={tutor.id} value={tutor.id}>
                        {tutorName(tutor)}
                      </option>
                    ))}
                  </Select>
                </span>
              ) : null}
            </>
          }
          className={styles.header}
        />
      ) : null}

      {student ? (
        <StudentLogin
          studentId={student.id}
          studentName={student.name}
          userId={loginUserId}
          email={login.data?.email ?? null}
        />
      ) : null}

      <Tabs label="Student sections" items={tabs} panelId={PANEL_ID} />
      <TabPanel id={PANEL_ID}>
        <Outlet context={{ studentId: id }} />
      </TabPanel>

      <StudentDialog
        open={editOpen}
        onClose={() => {
          setEditOpen(false);
        }}
        student={student}
      />

      <ConfirmDialog
        open={confirmArchive}
        onClose={() => {
          setConfirmArchive(false);
        }}
        title={isArchived ? "Bring this student back?" : "Archive this student?"}
        message={
          isArchived
            ? "They return to your active list."
            : "They leave your active list. Sessions, material and work are all kept, and you can bring them back at any time."
        }
        confirmLabel={isArchived ? "Unarchive" : "Archive"}
        danger={!isArchived}
        onConfirm={toggleArchive}
      />
    </div>
  );
}
