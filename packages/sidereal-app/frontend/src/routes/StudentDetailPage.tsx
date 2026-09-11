import { useMemo, useState } from "react";
import { Link, Outlet, useParams } from "react-router-dom";
import { toast } from "sonner";

import { StudentDialog } from "@/components/students/StudentDialog";
import { Button, ConfirmDialog, Spinner, StatusChip, TabPanel, Tabs } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useStudent, useUpdateStudent } from "@/lib/queries";

import pageStyles from "./page.module.css";
import styles from "./StudentDetailPage.module.css";

const PANEL_ID = "student-sections";

export function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: student, isLoading, isError } = useStudent(id);
  const updateStudent = useUpdateStudent();
  const [editOpen, setEditOpen] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

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

  const toggleArchive = async () => {
    try {
      await updateStudent.mutateAsync({ id, patch: { status: isArchived ? "active" : "archived" } });
      toast.success(isArchived ? `${student?.name ?? "Student"} is active again` : `${student?.name ?? "Student"} archived`);
    } catch (error) {
      toast.error(apiError(error));
      throw error;
    }
  };

  return (
    <div>
      <Link to="/students" className={pageStyles.back}>
        ← All students
      </Link>

      {isLoading ? (
        <p className={pageStyles.loading}>
          <Spinner /> Loading student…
        </p>
      ) : null}
      {isError ? <p className={pageStyles.status}>Could not load this student.</p> : null}

      {student ? (
        <header className={styles.header}>
          <div className={styles.titleRow}>
            <div className={styles.title}>
              <h1 className={pageStyles.heading}>{student.name}</h1>
              <StatusChip status={student.status} />
            </div>
            <div className={styles.actions}>
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
            </div>
          </div>
          <p className={pageStyles.meta}>
            <span>{student.level ?? "No level set"}</span>
            {(student.subjects ?? []).map((subject) => (
              <span key={subject} className={styles.subject}>
                {subject}
              </span>
            ))}
          </p>
        </header>
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
            ? "They will show up in your active list again. Nothing else changes."
            : "They drop out of your active list. Their sessions, material and work are all kept, and you can bring them back at any time."
        }
        confirmLabel={isArchived ? "Unarchive" : "Archive"}
        danger={!isArchived}
        onConfirm={toggleArchive}
      />
    </div>
  );
}
