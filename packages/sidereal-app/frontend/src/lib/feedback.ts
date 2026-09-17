function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

/** The title of the homework a piece of feedback is about, as far as the SDK expanded it. */
export function feedbackHomework(value: unknown): { id: string; title: string } | null {
  const row = asRecord(value);
  const id = row?.["id"];
  if (row === null || typeof id !== "string") {
    return null;
  }
  const title = row["title"];
  return { id, title: typeof title === "string" && title ? title : "Untitled homework" };
}

/**
 * Feedback has no title of its own. The homework it is about names it; failing that, its first
 * written line does — which is how every piece of feedback came to be called "Hi Leo,".
 */
export function feedbackTitle(feedback: { content: string | null; homework?: unknown }): string {
  const homework = feedbackHomework(feedback.homework);
  if (homework) {
    return homework.title;
  }
  const line = (feedback.content ?? "").split("\n").find((part) => part.trim() !== "");
  return line ? line.replace(/^#+\s*/, "").trim() : "Feedback from your tutor";
}
