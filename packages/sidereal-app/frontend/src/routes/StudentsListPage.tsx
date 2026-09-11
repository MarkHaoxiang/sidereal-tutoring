import { readItems } from "@directus/sdk";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/EmptyState";
import { directus } from "@/lib/directus";

import styles from "./StudentsListPage.module.css";

export function StudentsListPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["students"],
    queryFn: () => directus.request(readItems("students", { sort: ["name"] })),
  });

  return (
    <div>
      <h1 className={styles.heading}>Students</h1>

      {isLoading ? <p className={styles.status}>Loading students…</p> : null}
      {isError ? <p className={styles.status}>Could not load students. Try refreshing the page.</p> : null}

      {data && data.length === 0 ? (
        <EmptyState message="No students yet. Add a student in the Directus admin app to see them here." />
      ) : null}

      {data && data.length > 0 ? (
        <ul className={styles.list}>
          {data.map((student) => (
            <li key={student.id}>
              <Link to={`/students/${student.id}`} className={styles.card}>
                <span className={styles.name}>{student.name}</span>
                <span className={styles.meta}>
                  {student.level ?? "No level set"} · {student.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
