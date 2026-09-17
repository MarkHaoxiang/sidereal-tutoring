import { Button, ConfidenceChip, Markdown } from "@/components/ui";
import type { Transcription } from "@/lib/schema";
import { transcriptionText } from "@/lib/transcription";

import styles from "./student.module.css";

export interface TranscriptionPanelProps {
  transcription: Transcription;
  /**
   * Only for a sheet with no questions to divide it between: with questions, each answer
   * box has its own Insert here, so no button here could say which box it would fill.
   */
  onInsert?: (text: string) => void;
}

/** What the photo says. It is never written into the answers except by Insert. */
export function TranscriptionPanel({ transcription, onInsert }: TranscriptionPanelProps) {
  const text = transcriptionText(transcription);
  if (!text) {
    return null;
  }

  return (
    <section className={styles.transcript}>
      <div className={styles.transcriptHeader}>
        <h3 className={styles.transcriptTitle}>From your photo</h3>
        {transcription.confidence ? <ConfidenceChip confidence={transcription.confidence} /> : null}
        {onInsert ? (
          <Button
            size="sm"
            className={styles.insert}
            // The caret stays where the student left it, so Insert lands there.
            onMouseDown={(event) => {
              event.preventDefault();
            }}
            onClick={() => {
              onInsert(text);
            }}
          >
            Insert here
          </Button>
        ) : null}
      </div>
      <Markdown transcribed>{text}</Markdown>
    </section>
  );
}
