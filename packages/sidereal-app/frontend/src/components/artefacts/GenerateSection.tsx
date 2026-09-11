import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button, EmptyState } from "@/components/ui";
import type { GenerationJobKind } from "@/lib/schema";

import { GenerateDialog } from "./GenerateDialog";
import { GenerationProgress } from "./GenerationProgress";
import { ARTEFACT_KINDS } from "./kinds";
import styles from "./artefacts.module.css";

export interface GenerateSectionProps {
  studentId: string;
  kind: GenerationJobKind;
  /** Nothing generated yet: the button moves into the empty state, so there is one. */
  empty: boolean;
  emptyMessage: string;
}

export function GenerateSection({ studentId, kind, empty, emptyMessage }: GenerateSectionProps) {
  const copy = ARTEFACT_KINDS[kind];
  const navigate = useNavigate();
  const [asking, setAsking] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const open = useCallback(() => {
    setAsking(true);
  }, []);

  const done = useCallback(
    (artefactId: string) => {
      setJobId(null);
      void navigate(`/students/${studentId}/${copy.route}/${artefactId}`);
    },
    [navigate, studentId, copy.route]
  );

  const tryAgain = useCallback(() => {
    setJobId(null);
    setAsking(true);
  }, []);

  const button = (
    <Button variant="primary" onClick={open}>
      {copy.generateLabel}
    </Button>
  );

  return (
    <>
      {jobId ? (
        <GenerationProgress jobId={jobId} kind={kind} onDone={done} onTryAgain={tryAgain} />
      ) : empty ? (
        <EmptyState message={emptyMessage} action={button} />
      ) : (
        <div className={styles.actions}>{button}</div>
      )}
      <GenerateDialog
        open={asking}
        studentId={studentId}
        kind={kind}
        onStarted={setJobId}
        onClose={() => {
          setAsking(false);
        }}
      />
    </>
  );
}
