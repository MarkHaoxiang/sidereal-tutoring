import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { StudentDialog } from "@/components/students/StudentDialog";
import { Button, EmptyState, Input, Select, Spinner, StatusChip } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { useSessions, useStudents } from "@/lib/queries";
import type { StudentStatus } from "@/lib/schema";

import pageStyles from "./page.module.css";
import styles from "./StudentsListPage.module.css";

const STATUS_OPTIONS: { value: StudentStatus | "all"; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "archived", label: "Archived" },
  { value: "all", label: "Everyone" },
];

export function StudentsListPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StudentStatus | "all">("active");
  const [addOpen, setAddOpen] = useState(false);

  const students = useStudents(status === "all" ? {} : { status });

  // One query answers "next session" for every row.
  const now = useMemo(() => new Date().toISOString(), []);
  const upcoming = useSessions({ status: "scheduled", from: now, sort: "scheduled_at" });
  const nextSessionByStudent = useMemo(() => {
    const map = new Map<string, string>();
    for (const session of upcoming.data ?? []) {
      const studentId = session.student?.id;
      if (studentId && !map.has(studentId) && session.scheduled_at) {
        map.set(studentId, session.scheduled_at);
      }
    }
    return map;
  }, [upcoming.data]);

  const term = search.trim().toLowerCase();
  const visible = (students.data ?? []).filter((student) => student.name.toLowerCase().includes(term));

  return (
    <div>
      <div className={pageStyles.header}>
        <h1 className={pageStyles.heading}>Students</h1>
        <Button
          variant="primary"
          onClick={() => {
            setAddOpen(true);
          }}
        >
          Add student
        </Button>
      </div>

      <div className={styles.toolbar}>
        <Input
          type="search"
          value={search}
          placeholder="Search by name"
          aria-label="Search students by name"
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
        <Select
          value={status}
          aria-label="Filter by status"
          className={styles.filter}
          onChange={(event) => {
            setStatus(event.target.value as StudentStatus | "all");
          }}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      {students.isLoading ? (
        <p className={pageStyles.loading}>
          <Spinner /> Loading students…
        </p>
      ) : null}
      {students.isError ? (
        <p className={pageStyles.status}>Could not load students. Try refreshing the page.</p>
      ) : null}

      {students.data && visible.length === 0 ? (
        <EmptyState
          message={
            term
              ? `No students match “${search.trim()}”.`
              : "No students here yet. Add your first student to get started."
          }
          action={
            term ? null : (
              <Button
                variant="primary"
                onClick={() => {
                  setAddOpen(true);
                }}
              >
                Add student
              </Button>
            )
          }
        />
      ) : null}

      {visible.length > 0 ? (
        <ul className={styles.list}>
          {visible.map((student) => {
            const nextSession = nextSessionByStudent.get(student.id);
            return (
              <li key={student.id}>
                <Link to={`/students/${student.id}/overview`} className={styles.row}>
                  <span className={styles.top}>
                    <span className={styles.name}>{student.name}</span>
                    <StatusChip status={student.status} />
                  </span>
                  <span className={styles.detail}>{student.level ?? "No level set"}</span>
                  {student.subjects && student.subjects.length > 0 ? (
                    <span className={styles.subjects}>
                      {student.subjects.map((subject) => (
                        <span key={subject} className={styles.subject}>
                          {subject}
                        </span>
                      ))}
                    </span>
                  ) : null}
                  <span className={styles.detail}>
                    {nextSession ? `Next session ${formatDate(nextSession)}` : "No session scheduled"}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}

      <StudentDialog
        open={addOpen}
        onClose={() => {
          setAddOpen(false);
        }}
      />
    </div>
  );
}
