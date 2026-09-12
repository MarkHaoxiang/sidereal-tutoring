import { TopicChips } from "@/components/topics/TopicChips";
import { taggedTopics } from "@/components/topics/tree";
import { useGeneratedQuestions } from "@/lib/queries";
import type { HomeworkDetail } from "@/lib/queries";

import styles from "./artefacts.module.css";

interface QuestionRow {
  id: string;
  text: string;
  answer: string | null;
  topics: { id: string; name: string }[];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

/** The rows of the `homework_questions` junction, as far as they were expanded. */
function linkedQuestions(value: unknown): QuestionRow[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((entry) => {
    const question = asRecord(asRecord(entry)?.["question"]);
    if (!question) {
      return [];
    }
    const text = question["text"];
    if (typeof text !== "string") {
      return [];
    }
    const id = question["id"];
    const answer = question["answer"];
    return [
      {
        id: typeof id === "string" ? id : text,
        text,
        answer: typeof answer === "string" ? answer : null,
        topics: taggedTopics(question["topics"]),
      },
    ];
  });
}

export function HomeworkQuestions({ homework }: { homework: HomeworkDetail }) {
  const linked = linkedQuestions(homework.questions);
  const generated = homework.generated_from;
  const generatedIds = Array.isArray(generated?.questions) ? generated.questions : [];
  const byId = useGeneratedQuestions(linked.length > 0 ? [] : generatedIds);

  const rows: QuestionRow[] =
    linked.length > 0
      ? linked
      : (byId.data ?? []).map((row) => ({
          id: row.id,
          text: row.text,
          answer: row.answer,
          topics: taggedTopics(row.topics),
        }));

  if (rows.length === 0) {
    return null;
  }

  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Questions</h2>
      </div>
      <ol className={styles.questions}>
        {rows.map((row) => (
          <li key={row.id} className={styles.question}>
            {row.text}
            {row.answer ? <span className={styles.answer}>Answer: {row.answer}</span> : null}
            {row.topics.length > 0 ? <TopicChips topics={row.topics} className={styles.questionTopics} /> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
