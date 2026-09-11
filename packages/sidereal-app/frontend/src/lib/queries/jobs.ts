import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api";
import type { GenerationJobKind } from "@/lib/schema";

import { pollWhile } from "./poll";

export const jobKeys = {
  all: ["jobs"] as const,
  detail: (id: string) => ["jobs", "detail", id] as const,
};

async function fetchJob(jobId: string) {
  return unwrap(await api.GET("/api/jobs/{job_id}", { params: { path: { job_id: jobId } } }));
}

export type Job = Awaited<ReturnType<typeof fetchJob>>;

export interface CreateJobInput {
  kind: GenerationJobKind;
  student_id: string;
  document_ids: string[];
  instructions?: string | null;
  period_start?: string | null;
  period_end?: string | null;
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

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, ...body }: CreateJobInput) =>
      unwrap(await api.POST("/api/jobs/{kind}", { params: { path: { kind } }, body })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: jobKeys.all });
    },
  });
}
