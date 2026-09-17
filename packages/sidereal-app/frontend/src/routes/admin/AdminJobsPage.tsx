import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";
import { toast } from "sonner";

import { Button, EmptyState, PageHeader, Select, SkeletonRows, STATUS_TOKENS, StatusChip } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { useMediaQuery } from "@/lib/media";
import { apiError } from "@/lib/api";
import { useAdminJobs, useRetryJob } from "@/lib/queries";
import type { AdminJobStatus } from "@/lib/queries";

import pageStyles from "../page.module.css";
import styles from "./table.module.css";

const WIDE = "(min-width: 40rem)";

const STATUS_OPTIONS: { value: AdminJobStatus | "all"; label: string }[] = [
  { value: "all", label: "Every job" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Generating" },
  { value: "succeeded", label: "Done" },
  { value: "failed", label: "Failed" },
];

function JobDetail({ id, error, input }: { id: string; error: string | null | undefined; input: unknown }) {
  const again = useRetryJob();

  const retry = async () => {
    try {
      await again.mutateAsync(id);
      toast.success("Running");
    } catch (failure) {
      toast.error(apiError(failure));
    }
  };

  return (
    <>
      {error ? (
        <>
          <div className={styles.errorHeader}>
            <p className={styles.errorLabel}>Error</p>
            <Button
              size="sm"
              loading={again.isPending}
              onClick={() => {
                void retry();
              }}
            >
              Retry
            </Button>
          </div>
          <p className={styles.error}>{error}</p>
        </>
      ) : null}
      <p className={styles.detailLabel}>Input</p>
      <pre className={styles.pre}>{JSON.stringify(input ?? {}, null, 2)}</pre>
    </>
  );
}

export function AdminJobsPage() {
  const [status, setStatus] = useState<AdminJobStatus | "all">("all");
  const [expanded, setExpanded] = useState<string[]>([]);
  const wide = useMediaQuery(WIDE);
  const {
    data: jobs,
    isLoading,
    isError,
    isFetching,
    refetch,
  } = useAdminJobs(status === "all" ? {} : { status });

  const toggle = (id: string) => {
    setExpanded((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id]
    );
  };

  return (
    <div>
      <PageHeader title="Jobs" />

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
        <Button
          loading={isFetching}
          onClick={() => {
            void refetch();
          }}
        >
          Refresh
        </Button>
        {jobs ? <span className={styles.count}>{jobs.length} shown</span> : null}
      </div>

      {isLoading ? <SkeletonRows count={4} variant="line" label="Loading the jobs" /> : null}
      {isError ? <p className={pageStyles.status}>Could not load the jobs.</p> : null}

      {jobs && jobs.length === 0 ? (
        <EmptyState
          message={
            status === "all" ? "Nothing generated yet." : "No jobs with that status."
          }
        />
      ) : null}

      {jobs && jobs.length > 0 && wide ? (
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
                      <td>{student_name ?? "—"}</td>
                      <td className={styles.secondaryCell}>{tutor_email ?? "—"}</td>
                      <td className={styles.secondaryCell}>{job.model ?? "—"}</td>
                      <td className={styles.secondaryCell}>{formatDateTime(job.date_created ?? null)}</td>
                    </tr>
                    {open ? (
                      <tr className={styles.detailRow}>
                        <td colSpan={6}>
                          <div className={styles.detail}>
                            <JobDetail id={job.id} error={job.error} input={job.input} />
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

      {jobs && jobs.length > 0 && !wide ? (
        <div className={styles.cards} role="list" aria-label="Generation jobs">
          {jobs.map(({ job, student_name, tutor_email }) => {
            const open = expanded.includes(job.id);
            return (
              <article key={job.id} className={styles.card} role="listitem">
                <div className={styles.cardHeader}>
                  <span className={styles.primary}>{STATUS_TOKENS[job.kind].label}</span>
                  <StatusChip status={job.status ?? "queued"} />
                </div>
                <div className={styles.cardField}>
                  <span className={styles.cardFieldLabel}>Student</span>
                  <span>{student_name ?? "—"}</span>
                </div>
                <div className={styles.cardField}>
                  <span className={styles.cardFieldLabel}>Tutor</span>
                  <span className={styles.secondaryCell}>{tutor_email ?? "—"}</span>
                </div>
                <div className={styles.cardField}>
                  <span className={styles.cardFieldLabel}>Model</span>
                  <span className={styles.secondaryCell}>{job.model ?? "—"}</span>
                </div>
                <div className={styles.cardField}>
                  <span className={styles.cardFieldLabel}>Started</span>
                  <span className={styles.secondaryCell}>{formatDateTime(job.date_created ?? null)}</span>
                </div>
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
                  Details
                </button>
                {open ? (
                  <div className={styles.cardDetail}>
                    <JobDetail id={job.id} error={job.error} input={job.input} />
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
