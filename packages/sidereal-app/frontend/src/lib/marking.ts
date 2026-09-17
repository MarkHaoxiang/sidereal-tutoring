import type { MarkedQuestion, Marking } from "@/lib/schema";

// `homework.marking` as the two surfaces read it: the tutor writes it on the homework page and
// the student reads it on theirs. The shape itself is in schema.ts, with the rest of the domain.

export type { MarkedQuestion, Marking };

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function asMarks(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function asQuestion(value: unknown, index: number): MarkedQuestion | null {
  const row = asRecord(value);
  if (!row) {
    return null;
  }
  const number = row["number"];
  const comment = row["comment"];
  return {
    number: typeof number === "string" && number ? number : String(index + 1),
    marks_awarded: asMarks(row["marks_awarded"]),
    marks_available: asMarks(row["marks_available"]),
    ...(typeof comment === "string" && comment.trim() ? { comment } : {}),
  };
}

/** A json column, however it reaches the page: the SDK types it, the API does not. */
export function readMarking(value: unknown): Marking | null {
  const row = asRecord(value);
  if (!row) {
    return null;
  }
  const questions = Array.isArray(row["questions"]) ? row["questions"] : [];
  const comment = row["comment"];
  return {
    questions: questions.flatMap((question, index) => {
      const parsed = asQuestion(question, index);
      return parsed ? [parsed] : [];
    }),
    total_awarded: asMarks(row["total_awarded"]),
    total_available: asMarks(row["total_available"]),
    ...(typeof comment === "string" && comment.trim() ? { comment } : {}),
  };
}

export function hasMarking(value: Marking | null): boolean {
  return value !== null && (value.questions.length > 0 || value.total_available > 0);
}

export function markingTotals(questions: MarkedQuestion[]): { awarded: number; available: number } {
  return questions.reduce(
    (total, question) => ({
      awarded: total.awarded + question.marks_awarded,
      available: total.available + question.marks_available,
    }),
    { awarded: 0, available: 0 }
  );
}

/** "5 / 20" for a homework that has been marked, or null for one that has not. */
export function markingLabel(value: unknown): string | null {
  const marking = readMarking(value);
  return marking !== null && hasMarking(marking)
    ? marksLabel(marking.total_awarded, marking.total_available)
    : null;
}

export function marksLabel(awarded: number, available: number): string {
  return `${String(awarded)} / ${String(available)}`;
}
