import type { TranscribedQuestion, Transcription, TranscriptionConfidence } from "@/lib/schema";
import { plainText } from "@/lib/typstText";

/** What the transcriber writes where it could not read the page. */
const UNREADABLE = "[?]";

const CONFIDENCES: TranscriptionConfidence[] = ["high", "medium", "low"];

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function asConfidence(value: unknown): TranscriptionConfidence | undefined {
  return CONFIDENCES.find((confidence) => confidence === value);
}

function asQuestion(value: unknown): TranscribedQuestion | null {
  const row = asRecord(value);
  const number = row?.["number"];
  const text = row?.["text"];
  const confidence = asConfidence(row?.["confidence"]);
  if (typeof number !== "string" || typeof text !== "string" || confidence === undefined) {
    return null;
  }
  const note = row?.["note"];
  return { number, text, confidence, ...(typeof note === "string" && note ? { note } : {}) };
}

/** A json column, however it reaches the page: the SDK types it, the API does not. */
export function readTranscription(value: unknown): Transcription | null {
  const row = asRecord(value);
  if (row === null) {
    return null;
  }
  const questions = Array.isArray(row["questions"]) ? row["questions"] : [];
  const text = row["text"];
  const confidence = asConfidence(row["confidence"]);
  return {
    ...(typeof text === "string" ? { text } : {}),
    ...(confidence ? { confidence } : {}),
    questions: questions.flatMap((question) => {
      const parsed = asQuestion(question);
      return parsed ? [parsed] : [];
    }),
  };
}

/** The whole of what the photo said, as one piece of markdown. */
export function transcriptionText(value: Transcription): string {
  const text = value.text?.trim();
  if (text) {
    return plainText(text);
  }
  return value.questions
    .map((question) => `**${question.number}** ${plainText(question.text)}`)
    .join("\n\n");
}

/** What the photo said for one question, when it was read question by question. */
export function questionTranscription(value: Transcription, number: number): string | null {
  const row = value.questions.find(
    (question) => Number.parseInt(question.number.replace(/[^0-9]/g, ""), 10) === number
  );
  return row ? plainText(row.text) : null;
}

export function hasTranscription(value: Transcription | null): boolean {
  return value !== null && (Boolean(value.text?.trim()) || value.questions.length > 0);
}

interface MarkdownNode {
  type: string;
  value?: string;
  children?: MarkdownNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

function marked(): MarkdownNode {
  return {
    type: "emphasis",
    data: { hName: "span", hProperties: { className: ["unreadable"] } },
    children: [{ type: "text", value: UNREADABLE }],
  };
}

function split(value: string): MarkdownNode[] {
  return value
    .split(UNREADABLE)
    .flatMap((piece, index) => [
      ...(index === 0 ? [] : [marked()]),
      ...(piece ? [{ type: "text", value: piece }] : []),
    ]);
}

function mark(node: MarkdownNode): void {
  if (!node.children) {
    return;
  }
  node.children = node.children.flatMap((child) => {
    if (child.type === "text" && child.value?.includes(UNREADABLE)) {
      return split(child.value);
    }
    mark(child);
    return [child];
  });
}

/** A remark plugin: the spans the transcriber could not read, marked where they sit. */
export function markUnreadable() {
  return (tree: unknown) => {
    mark(tree as MarkdownNode);
  };
}
