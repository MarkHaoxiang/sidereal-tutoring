import { Card, SkeletonRows } from "@/components/ui";
import { useMyStudent } from "@/lib/queries";

import styles from "./account.module.css";

/** What the tutor's record says about the student. Theirs to see, not to change. */
export function AboutYouCard() {
  const { data: student, isLoading, isError } = useMyStudent();
  const subjects = student?.subjects ?? [];

  return (
    <Card title="About you">
      {isLoading ? <SkeletonRows count={2} variant="line" label="Loading your details" /> : null}
      {isError || (!isLoading && !student) ? (
        <p className={styles.hint}>Could not load your details.</p>
      ) : null}

      {student ? (
        <>
          <dl className={styles.about}>
            <dt className={styles.aboutTerm}>Name</dt>
            <dd className={styles.aboutValue}>{student.name}</dd>

            <dt className={styles.aboutTerm}>Level</dt>
            <dd className={styles.aboutValue}>{student.level ?? "Not set"}</dd>

            <dt className={styles.aboutTerm}>Subjects</dt>
            <dd className={styles.aboutValue}>
              {subjects.length > 0 ? (
                <span className={styles.chips}>
                  {subjects.map((subject) => (
                    <span key={subject} className={styles.chip}>
                      {subject}
                    </span>
                  ))}
                </span>
              ) : (
                "Not set"
              )}
            </dd>
          </dl>
          <p className={styles.aboutHint}>Ask your tutor if any of this needs changing.</p>
        </>
      ) : null}
    </Card>
  );
}
