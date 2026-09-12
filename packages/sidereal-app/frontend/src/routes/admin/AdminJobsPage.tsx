import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";

import { EmptyState, PageHeader, Select, SkeletonRows, STATUS_TOKENS, StatusChip } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { useAdminJobs } from "@/lib/queries";
import type { AdminJobStatus } from "@/lib/queries";

import pageStyles from "../page.module.css";
import styles from "./table.module.css";

const STATUS_OPTIONS: { value: AdminJobStatus | "all"; label: string }[] = [
  { value: "all", label: "Every job" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Generating" },
  { value: "succeeded", label: "Done" },
  { value: "failed", label: "Failed" },
];

export function AdminJobsPage() {
  const [status, setStatus] = useState<AdminJobStatus | "all">("all");
  const [expanded, setExpanded] = useState<string[]>([]);
  const { data: jobs, isLoading, isError } = useAdminJobs(status === "all" ? {} : { status });

  const toggle = (id: string) => {
    setExpanded((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]
    );
  };

  return (
    <div>
      <PageHeader
        eyebrow="Admin"
        title="Jobs"
        subtitle="Every generation run in the practice, newest first. A queued or running one refreshes itself."
      />

      <div className={styles.toolbar}>
        <Select
          value={status}
          aria-label="Filter by status"
          className={styles.filter}
          onChange={(event) => {
            setStatus(event.target.value as AdminJobStatus | "all");
          }}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
        {jobs ? <span className={styles.count}>{jobs.length} shown</span> : null}
      </div>

      {isLoading ? <SkeletonRows count={4} variant="line" label="Loading the jobs" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load the jobs. Try refreshing the page.</p> : null}

      {jobs && jobs.length === 0 ? (
        <EmptyState
          message={
            status === "all"
              ? "Nothing has been generated yet."
              : "No jobs with that status right now."
          }
        />
      ) : null}

      {jobs && jobs.length > 0 ? (
        <div className={styles.scroller} tabIndex={0} role="region" aria-label="Generation jobs">
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Job</th>
                <th scope="col">Status</th>
                <th scope="col">Student</th>
                <th scope="col">Tutor</th>
                <th scope="col">Model</th>
                <th scope="col">Started</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(({ job, student_name, tutor_email }) => {
                const open = expanded.includes(job.id);
                return (
                  <Fragment key={job.id}>
                    <tr>
                      <td>
                        <button
                          type="button"
                          className={styles.twist}
                          aria-expanded={open}
                          onClick={() => {
                            toggle(job.id);
                          }}
                        >
                          {open ? (
                            <ChevronDown size={15} aria-hidden="true" />
                          ) : (
                            <ChevronRight size={15} aria-hidden="true" />
                          )}
                          {STATUS_TOKENS[job.kind].label}
                        </button>
                      </td>
                      <td>
                        <StatusChip status={job.status ?? "queued"} />
                      </td>
                      <td>{student_name ?? "No student"}</td>
                      <td className={styles.secondaryCell}>{tutor_email ?? "No tutor"}</td>
                      <td className={styles.secondaryCell}>{job.model ?? "No model recorded"}</td>
                      <td className={styles.secondaryCell}>{formatDateTime(job.date_created ?? null)}</td>
                    </tr>
                    {open ? (
                      <tr className={styles.detailRow}>
                        <td colSpan={6}>
                          <div className={styles.detail}>
                            {job.error ? (
                              <>
                                <p className={styles.detailLabel}>What went wrong</p>
                                <p className={styles.error}>{job.error}</p>
                              </>
                            ) : null}
                            <p className={styles.detailLabel}>What it was asked for</p>
                            <pre className={styles.pre}>{JSON.stringify(job.input ?? {}, null, 2)}</pre>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
