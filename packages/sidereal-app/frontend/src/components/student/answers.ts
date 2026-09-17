import type { StudentQuestion } from "./homework";

// `homework.submission` stays one text column: the per-question boxes are its `## Q<n>`
// sections, in the tutor's question order. Every section is written, empty or not, so the
// numbering the tutor reads never shifts.

const HEADING = /^[ \t]*##[ \t]+Q(\d+)[ \t]*$/;

/** The text for each box. A submission written as one blob belongs to the first. */
export function splitAnswers(
  submission: string | null | undefined,
  questions: readonly StudentQuestion[]
): string[] {
  const text = submission ?? "";
  if (questions.length === 0) {
    return [text];
  }

  const buckets: string[][] = questions.map(() => []);
  const preamble: string[] = [];
  let current = preamble;
  let found = 0;

  for (const line of text.split("\n")) {
    const number = HEADING.exec(line)?.[1];
    const bucket = buckets[found];
    if (number !== undefined && bucket !== undefined && Number(number) === found + 1) {
      current = bucket;
      found += 1;
      continue;
    }
    current.push(line);
  }

  if (found === 0) {
    return buckets.map((_, index) => (index === 0 ? text : ""));
  }

  // A section a heading closed carries the blank line `joinAnswers` put before that
  // heading; the last one carries nothing, so what the student typed comes back whole.
  const parts = buckets.map((lines, index) => {
    const closed = index + 1 < found;
    const last = lines.length - 1;
    return (closed && lines[last] === "" ? lines.slice(0, last) : lines).join("\n");
  });

  const lead = preamble.join("\n").trim();
  if (lead) {
    const first = parts[0] ?? "";
    parts[0] = first ? `${lead}\n\n${first}` : lead;
  }
  return parts;
}

/** The markdown to store. */
export function joinAnswers(
  parts: readonly string[],
  questions: readonly StudentQuestion[]
): string {
  if (questions.length === 0) {
    return parts[0] ?? "";
  }
  return questions
    .map((_, index) => `## Q${String(index + 1)}\n${parts[index] ?? ""}`)
    .join("\n\n");
}
