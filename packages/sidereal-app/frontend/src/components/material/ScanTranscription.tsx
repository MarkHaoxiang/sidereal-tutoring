import { FragmentView } from "@/components/papers/FragmentView";
import { structureQuestions } from "@/components/papers/draft";
import { ConfidenceChip, Markdown } from "@/components/ui";
import { cx } from "@/lib/cx";
import { plainText } from "@/lib/typstText";
import type { RenderBody } from "@/lib/queries";
import type { CanonicalPaper, Transcription } from "@/lib/schema";

import styles from "./scan.module.css";

export interface ScanTranscriptionProps {
  /** The whole of what was read; for a solutions scan the per-question working sits beside it. */
  text: string | null;
  transcription: Transcription | null;
  structure: CanonicalPaper | null;
  empty: string;
}

function questionBody(structure: CanonicalPaper | null, number: string): RenderBody | null {
  const question = structureQuestions(structure).find((candidate) => candidate.number === number);
  return question === undefined ? null : { kind: "question", document: question, output: "svg" };
}

/** What the model read off the pages: question by question when it was given a paper. */
export function ScanTranscription({ text, transcription, structure, empty }: ScanTranscriptionProps) {
  const questions = transcription?.questions ?? [];

  if (questions.length > 0) {
    return (
      <div className={styles.answers}>
        {questions.map((question) => (
          <article
            key={question.number}
            className={cx(styles.answer, question.confidence === "low" && styles.answerLow)}
          >
            <header className={styles.answerHeader}>
              <h3 className={styles.answerTitle}>Question {question.number}</h3>
              <ConfidenceChip confidence={question.confidence} />
            </header>
            <FragmentView
              body={questionBody(structure, question.number)}
              label={`question ${question.number}`}
              empty="This question is not in the paper."
            />
            <Markdown transcribed>{plainText(question.text)}</Markdown>
            {question.note ? <p className={styles.note}>{question.note}</p> : null}
          </article>
        ))}
      </div>
    );
  }

  return text ? <Markdown transcribed>{plainText(text)}</Markdown> : <p className={styles.quiet}>{empty}</p>;
}
