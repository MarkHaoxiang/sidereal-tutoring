import { ConfidenceChip } from "@/components/ui";
import { fileIdOf } from "@/lib/files";
import type { DocumentDetail } from "@/lib/queries";
import type { TranscriptionConfidence } from "@/lib/schema";

import { ScanPages } from "./ScanPages";
import { ScanTranscription } from "./ScanTranscription";
import styles from "./scan.module.css";

const CONFIDENCES: TranscriptionConfidence[] = ["high", "medium", "low"];

/** `documents.metadata.confidence`: how well the pages read, as a whole. */
function scanConfidence(metadata: Record<string, unknown> | null): TranscriptionConfidence | null {
  const value = metadata?.["confidence"];
  return CONFIDENCES.find((confidence) => confidence === value) ?? null;
}

/** A scan: the pages on the left, what was read off them on the right. */
export function ScanView({ document }: { document: DocumentDetail }) {
  const pages = [...(document.pages ?? [])].sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
  const fileIds = pages.flatMap((page) => {
    const fileId = fileIdOf(page.file);
    return fileId ? [fileId] : [];
  });
  const confidence = scanConfidence(document.metadata);
  const paper = typeof document.paper === "string" ? null : document.paper;

  return (
    <div className={styles.scan}>
      <ScanPages fileIds={fileIds} />
      <div className={styles.reading}>
        {confidence || paper ? (
          <div className={styles.readingHeader}>
            {paper ? <span className={styles.paper}>{paper.title}</span> : null}
            {confidence ? <ConfidenceChip confidence={confidence} /> : null}
          </div>
        ) : null}
        <ScanTranscription
          text={document.text}
          transcription={document.transcription}
          structure={paper?.structure ?? null}
          empty={document.status === "ready" ? "Nothing was read." : "Not read yet."}
        />
      </div>
    </div>
  );
}
