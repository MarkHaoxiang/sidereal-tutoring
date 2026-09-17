import type { MarkingQuestion } from "./Marking";

// What a homework says about where it came from: the `homework_questions` junction as far as
// the SDK expanded it, and the paper a worksheet was cut from.

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

/**
 * The paper this homework was cut from, when it was one. Such a sheet's source names figure
 * files that a plain recompile cannot carry, so it is read rather than edited.
 */
export function paperOf(generatedFrom: unknown): string | null {
  const paper = asRecord(generatedFrom)?.["paper"];
  return typeof paper === "string" && paper ? paper : null;
}

/** The questions to mark, in the tutor's order, each with the marks the paper gives it. */
export function markedQuestions(value: unknown): MarkingQuestion[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows = value.flatMap((entry, index) => {
    const link = asRecord(entry);
    const question = asRecord(link?.["question"]);
    if (!question) {
      return [];
    }
    const id = question["id"];
    const number = question["number"];
    const text = question["text"];
    const marks = question["marks"];
    const sort = link?.["sort"];
    return [
      {
        id: typeof id === "string" ? id : String(index),
        number: typeof number === "string" && number ? number : String(index + 1),
        text: typeof text === "string" ? text : null,
        marks: typeof marks === "number" ? marks : null,
        sort: typeof sort === "number" ? sort : Number.MAX_SAFE_INTEGER,
      },
    ];
  });
  return rows
    .sort((a, b) => a.sort - b.sort)
    .map((row) => ({ id: row.id, number: row.number, text: row.text, marks: row.marks }));
}
