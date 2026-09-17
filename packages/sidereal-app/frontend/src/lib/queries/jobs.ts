import { readItems } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api";
import { directus } from "@/lib/directus";
import type { GenerationJobKind, HomeworkFormat } from "@/lib/schema";

import { adminKeys } from "./admin";
import { pollWhile } from "./poll";

export const jobKeys = {
  all: ["jobs"] as const,
  detail: (id: string) => ["jobs", "detail", id] as const,
  student: (studentId: string, kind: GenerationJobKind) =>
    ["jobs", "student", studentId, kind] as const,
};

async function fetchJob(jobId: string) {
  return unwrap(await api.GET("/api/jobs/{job_id}", { params: { path: { job_id: jobId } } }));
}

export type Job = Awaited<ReturnType<typeof fetchJob>>;

export interface CreateJobInput {
  kind: GenerationJobKind;
  /** Every kind but `paper_extract`, which is filed against the library rather than a student. */
  student_id?: string | null;
  document_ids: string[];
  /** Feedback only: the hand-ins it is about — their questions, answers and marks. */
  homework_ids?: string[];
  instructions?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  /** Homework only; the app answers 422 for any other kind asked to be Typst. */
  format?: HomeworkFormat;
  /**
   * Extracting a paper only, and 422 on any other kind even as `false`: whether the pages are
   * read as images. Null leaves the choice to the extractor.
   */
  pages?: boolean | null;
}

/** Polls until the job settles; pass `null` while nothing is running. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: jobKeys.detail(jobId ?? ""),
    queryFn: () => fetchJob(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: pollWhile<Job>((job) => job.status === "queued" || job.status === "running", 1500),
  });
}

// The rows a tab shows above its list: what is still running, and what failed. A run outlives
// the tab that started it, so this — not the job id in that tab's state — is what survives a
// refresh.
function fetchStudentJobs(studentId: string, kind: GenerationJobKind) {
  return directus.request(
    readItems("generation_jobs", {
      fields: ["id", "kind", "status", "error", "model", "output_id", "date_created"],
      filter: { student: { _eq: studentId }, kind: { _eq: kind } },
      sort: ["-date_created"],
      limit: 10,
    })
  );
}

export type StudentJob = Awaited<ReturnType<typeof fetchStudentJobs>>[number];

const isUnsettled = (job: StudentJob) => job.status === "queued" || job.status === "running";

/** Queued, running and failed jobs for one student and kind, newest first. */
export function useStudentJobs(studentId: string, kind: GenerationJobKind) {
  return useQuery({
    queryKey: jobKeys.student(studentId, kind),
    queryFn: async () => (await fetchStudentJobs(studentId, kind)).filter((job) => job.status !== "succeeded"),
    enabled: Boolean(studentId),
    refetchInterval: pollWhile<StudentJob[]>((jobs) => jobs.some(isUnsettled), 3000),
  });
}

/** Runs the same input again as a new job; the failed row stays where it is. */
export function useRetryJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: string) =>
      unwrap(await api.POST("/api/jobs/{job_id}/retry", { params: { path: { job_id: jobId } } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobKeys.all });
      void queryClient.invalidateQueries({ queryKey: adminKeys.all });
    },
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    // `format` is sent every time rather than left to the server's default, so the request
    // says what it wants and the generated client has nothing optional to guess at.
    mutationFn: async ({ kind, format = "markdown", ...rest }: CreateJobInput) =>
      unwrap(await api.POST("/api/jobs/{kind}", { params: { path: { kind } }, body: { ...rest, format } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobKeys.all });
    },
  });
}
