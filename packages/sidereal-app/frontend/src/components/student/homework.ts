import { formatDate } from "@/lib/format";
import type { HomeworkStatus } from "@/lib/schema";

// What the student view needs to say about a piece of homework: when it is due, whether
// that date has passed, and the questions to answer. `due_on` is a calendar date, so it
// is compared as one — an hour either side of midnight must not change the answer.

export interface DueHomework {
  due_on: string | null;
  status: HomeworkStatus;
}

export interface StudentQuestion {
  id: string;
  text: string;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function todayKey(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${String(now.getFullYear())}-${month}-${day}`;
}

export function isOverdue(homework: DueHomework): boolean {
  return homework.status === "assigned" && homework.due_on !== null && homework.due_on < todayKey();
}

export function dueLabel(dueOn: string | null): string {
  return dueOn ? `Due ${formatDate(dueOn)}` : "No due date";
}

/** Soonest first, with the undated ones after everything that has a date. */
export function byDueDate(a: DueHomework, b: DueHomework): number {
  if (a.due_on === b.due_on) {
    return 0;
  }
  if (!a.due_on) {
    return 1;
  }
  if (!b.due_on) {
    return -1;
  }
  return a.due_on < b.due_on ? -1 : 1;
}

/**
 * The questions behind the `homework_questions` junction, in the tutor's order. The SDK
 * types a nested alias field loosely, so the rows are read defensively; `answer` is the
 * mark scheme and is never fetched, so it cannot appear here.
 */
export function homeworkQuestions(value: unknown): StudentQuestion[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows = value.flatMap((entry) => {
    const link = asRecord(entry);
    const question = asRecord(link?.["question"]);
    const text = question?.["text"];
    if (!question || typeof text !== "string") {
      return [];
    }
    const id = question["id"];
    const sort = link?.["sort"];
    return [
      {
        id: typeof id === "string" ? id : text,
        text,
        sort: typeof sort === "number" ? sort : Number.MAX_SAFE_INTEGER,
      },
    ];
  });
  return rows.sort((a, b) => a.sort - b.sort).map(({ id, text }) => ({ id, text }));
}
