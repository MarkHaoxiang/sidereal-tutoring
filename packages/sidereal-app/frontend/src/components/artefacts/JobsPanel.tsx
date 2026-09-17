import { useState } from "react";
import { toast } from "sonner";

import { Button, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import { formatDateTime } from "@/lib/format";
import { useRetryJob, useStudentJobs } from "@/lib/queries";
import type { StudentJob } from "@/lib/queries";

import type { ArtefactKind } from "./kinds";
import styles from "./jobs.module.css";

export interface JobsPanelProps {
  studentId: string;
  kind: ArtefactKind;
}

/**
 * Queued, running and failed jobs for this student and kind — rows come straight from
 * `generation_jobs`, so a refresh cannot lose them the way a tab's own state would.
 */
export function JobsPanel({ studentId, kind }: JobsPanelProps) {
  const { data: jobs } = useStudentJobs(studentId, kind);
  const again = useRetryJob();
  const [retryingId, setRetryingId] = useState<string | null>(null);

  if (!jobs || jobs.length === 0) {
    return null;
  }

  const retry = (job: StudentJob) => {
    setRetryingId(job.id);
    again
      .mutateAsync(job.id)
      .then(() => {
        toast.success("Running");
      })
      .catch((error: unknown) => {
        toast.error(apiError(error));
      })
      .finally(() => {
        setRetryingId(null);
      });
  };

  return (
    <ul className={styles.panel}>
      {jobs.map((job) => (
        <li key={job.id} className={cx(styles.row, job.status === "failed" && styles.failed)}>
          <div className={styles.summary}>
            <span className={styles.status}>
              <StatusChip status={job.status} />
              <span className={styles.started}>{formatDateTime(job.date_created)}</span>
            </span>
            {job.status === "failed" ? (
              <Button
                size="sm"
                loading={retryingId === job.id}
                onClick={() => {
                  retry(job);
                }}
              >
                Retry
              </Button>
            ) : null}
          </div>
          {job.status === "failed" ? (
            <p className={styles.error}>{job.error ?? "The generation did not finish."}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
