import { Button, ConfidenceChip, Markdown } from "@/components/ui";
import type { Transcription } from "@/lib/schema";
import { plainText } from "@/lib/typstText";

import styles from "./student.module.css";

export interface TranscriptionPanelProps {
  transcription: Transcription;
  /** Left out once the homework is in: there is no box left to insert into. */
  onInsert?: (text: string) => void;
}

function readable(value: Transcription): string {
  const text = value.text?.trim();
  if (text) {
    return plainText(text);
  }
  return value.questions
    .map((question) => `**${question.number}** ${plainText(question.text)}`)
    .join("\n\n");
}

/** What the photo says. It is never written into the answers except by Insert. */
export function TranscriptionPanel({ transcription, onInsert }: TranscriptionPanelProps) {
  const text = readable(transcription);
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
            Insert
          </Button>
        ) : null}
      </div>
      <Markdown transcribed>{text}</Markdown>
    </section>
  );
}
