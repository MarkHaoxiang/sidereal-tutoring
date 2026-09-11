/** Feedback has no title of its own, so its first written line stands in for one. */
export function feedbackTitle(content: string | null): string {
  const line = (content ?? "").split("\n").find((part) => part.trim() !== "");
  return line ? line.replace(/^#+\s*/, "").trim() : "Feedback from your tutor";
}
