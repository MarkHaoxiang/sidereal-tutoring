import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { Button, Spinner } from "@/components/ui";
import { useJob } from "@/lib/queries";
import type { GenerationJobKind } from "@/lib/schema";

import { ARTEFACT_KINDS } from "./kinds";
import styles from "./artefacts.module.css";

export interface GenerationProgressProps {
  jobId: string;
  kind: GenerationJobKind;
  /** Called once, with the id of what was generated. */
  onDone: (artefactId: string) => void;
  onTryAgain: () => void;
}

export function GenerationProgress({ jobId, kind, onDone, onTryAgain }: GenerationProgressProps) {
  const queryClient = useQueryClient();
  const { data: job, isError } = useJob(jobId);
  const artefactId = job?.status === "succeeded" ? (job.output_id ?? null) : null;

  useEffect(() => {
    if (!artefactId) {
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ARTEFACT_KINDS[kind].listKey });
    onDone(artefactId);
  }, [artefactId, kind, onDone, queryClient]);

  const failure = isError
    ? "This generation could not be checked on. It may still be running."
    : job?.status === "failed"
      ? (job.error ?? "The generation did not finish.")
      : job?.status === "succeeded" && !job.output_id
        ? "The generation finished but produced nothing."
        : null;

  return (
    <div className={styles.progress}>
      {failure === null ? (
        <p className={styles.progressText}>
          <Spinner /> Generating… this usually takes under a minute.
        </p>
      ) : (
        <>
          <p className={styles.failedText}>{failure}</p>
          <Button variant="primary" onClick={onTryAgain}>
            Try again
          </Button>
        </>
      )}
    </div>
  );
}
