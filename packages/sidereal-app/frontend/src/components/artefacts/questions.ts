import { plainText } from "@/lib/typstText";

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

// Words of three letters or more, which survive a change of markup where punctuation and
// symbols do not: "$50 \"N\"$" and "50 N" share nothing, "the beam" shares both words.
const WORDS = /[a-z]{3,}/g;

const ENOUGH = 4;
const SAME = 0.8;

function stillSet(text: string, sheet: string): boolean {
  const words = [...new Set(plainText(text).toLowerCase().match(WORDS) ?? [])];
  if (words.length < ENOUGH) {
    return true;
  }
  const found = words.filter((word) => sheet.includes(word)).length;
  return found / words.length >= SAME;
}

/**
 * Whether the sheet has been rewritten since these questions were taken from it. The rows
 * are written once, and the marking panel and the generated feedback both read them, so a
 * question that is no longer on the sheet is worth saying out loud.
 */
export function editedSince(content: string | null, questions: readonly { text: string }[]): boolean {
  const sheet = plainText(content).toLowerCase();
  if (sheet.trim() === "" || questions.length === 0) {
    return false;
  }
  return questions.some((question) => !stillSet(question.text, sheet));
}
