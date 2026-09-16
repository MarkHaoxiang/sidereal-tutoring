import type { PaperDetail, PaperPatch } from "@/lib/queries";
import type {
  CanonicalMarkScheme,
  CanonicalMarkSchemePart,
  CanonicalMarkSchemeQuestion,
  CanonicalPaper,
  CanonicalPart,
  CanonicalQuestion,
} from "@/lib/schema";

// The renderer's cap, mirroring sidereal_core.canonical.MAX_ANSWER_LINES.
export const MAX_ANSWER_LINES = 60;

// Every number is held as the text in its input, so a half-typed value is still a value.
// `key` is React's, never Directus's: the structure it is stripped from has no ids.
export interface SubPartDraft {
  key: string;
  label: string;
  text: string;
  marks: string;
  answerLines: string;
}

export interface PartDraft extends SubPartDraft {
  parts: SubPartDraft[];
}

export interface QuestionDraft {
  key: string;
  number: string;
  stem: string;
  marks: string;
  answerLines: string;
  parts: PartDraft[];
}

export interface SchemePartDraft {
  key: string;
  label: string;
  answer: string;
  marks: string;
  notes: string;
}

export interface SchemeQuestionDraft {
  key: string;
  number: string;
  answer: string;
  notes: string;
  parts: SchemePartDraft[];
}

export interface PaperDraft {
  title: string;
  source: string;
  board: string;
  year: string;
  timeMinutes: string;
  totalMarks: string;
  instructions: string;
  questions: QuestionDraft[];
  scheme: SchemeQuestionDraft[];
}

let counter = 0;

function key(): string {
  counter += 1;
  return `k${String(counter)}`;
}

function text(value: string | null | undefined): string {
  return value ?? "";
}

function num(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

function subPartDraft(part: CanonicalPart): SubPartDraft {
  return {
    key: key(),
    label: part.label,
    text: part.text,
    marks: num(part.marks),
    answerLines: num(part.answer_lines),
  };
}

export function emptySubPart(): SubPartDraft {
  return { key: key(), label: "", text: "", marks: "", answerLines: "" };
}

export function emptyPart(): PartDraft {
  return { ...emptySubPart(), parts: [] };
}

export function emptyQuestion(): QuestionDraft {
  return { key: key(), number: "", stem: "", marks: "", answerLines: "", parts: [] };
}

export function emptySchemePart(): SchemePartDraft {
  return { key: key(), label: "", answer: "", marks: "", notes: "" };
}

export function emptySchemeQuestion(): SchemeQuestionDraft {
  return { key: key(), number: "", answer: "", notes: "", parts: [] };
}

/** The row as the editor holds it. The structure is the source of truth; the columns follow it. */
export function paperDraft(paper: PaperDetail): PaperDraft {
  const structure: CanonicalPaper | null = paper.structure;
  const scheme: CanonicalMarkScheme | null = paper.mark_scheme;
  return {
    title: structure?.title ?? paper.title,
    source: text(structure?.source ?? paper.source),
    board: text(structure?.board ?? paper.board),
    year: num(structure?.year ?? paper.year),
    timeMinutes: num(structure?.time_minutes ?? paper.time_minutes),
    totalMarks: num(structure?.total_marks ?? paper.total_marks),
    instructions: text(structure?.instructions ?? paper.instructions),
    questions: (structure?.questions ?? []).map((question) => ({
      key: key(),
      number: question.number,
      stem: text(question.stem),
      marks: num(question.marks),
      answerLines: num(question.answer_lines),
      parts: (question.parts ?? []).map((part) => ({
        ...subPartDraft(part),
        parts: (part.parts ?? []).map(subPartDraft),
      })),
    })),
    scheme: (scheme?.questions ?? []).map((question) => ({
      key: key(),
      number: question.number,
      answer: text(question.answer),
      notes: text(question.notes),
      parts: (question.parts ?? []).map((part) => ({
        key: key(),
        label: part.label,
        answer: part.answer,
        marks: num(part.marks),
        notes: text(part.notes),
      })),
    })),
  };
}

/** A copy of `list` with the item at `index` one place earlier or later. */
export function moved<T>(list: T[], index: number, delta: -1 | 1): T[] {
  const target = index + delta;
  if (target < 0 || target >= list.length) {
    return list;
  }
  const next = [...list];
  const [item] = next.splice(index, 1);
  if (item === undefined) {
    return list;
  }
  next.splice(target, 0, item);
  return next;
}

export type Built =
  | { ok: true; patch: PaperPatch }
  | { ok: false; problems: string[] };

class Problems {
  readonly all: string[] = [];

  add(message: string): void {
    this.all.push(message);
  }

  /** A whole number, or null when the field is empty. */
  whole(value: string, where: string, max?: number): number | null {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    if (!Number.isInteger(parsed) || parsed < 0) {
      this.add(`${where} must be a whole number, or left empty.`);
      return null;
    }
    if (max !== undefined && parsed > max) {
      this.add(`${where} is at most ${String(max)}.`);
      return null;
    }
    return parsed;
  }

  required(value: string, where: string): string {
    const trimmed = value.trim();
    if (!trimmed) {
      this.add(where);
    }
    return trimmed;
  }
}

function optional(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function buildQuestion(
  question: QuestionDraft,
  index: number,
  problems: Problems
): CanonicalQuestion {
  const at = `Question ${question.number.trim() || String(index + 1)}`;
  const number = problems.required(question.number, `${at} needs a number.`);
  const parts: CanonicalPart[] = question.parts.map((part) => {
    const partAt = `${at}, part ${part.label.trim() || "?"}`;
    const subParts: CanonicalPart[] = part.parts.map((sub) => {
      const subAt = `${partAt} (${sub.label.trim() || "?"})`;
      // A sub-part carries no parts of its own: the structure nests one level only.
      const builtSub: CanonicalPart = {
        label: problems.required(sub.label, `${subAt} needs a label.`),
        text: problems.required(sub.text, `${subAt} needs to say what it asks.`),
      };
      const subMarks = problems.whole(sub.marks, `${subAt}'s marks`);
      if (subMarks !== null) {
        builtSub.marks = subMarks;
      }
      const subLines = problems.whole(sub.answerLines, `${subAt}'s answer lines`, MAX_ANSWER_LINES);
      if (subLines !== null) {
        builtSub.answer_lines = subLines;
      }
      return builtSub;
    });

    // A part that only groups sub-parts asks nothing itself, so its text may be empty.
    const built: CanonicalPart = {
      label: problems.required(part.label, `${partAt} needs a label.`),
      text: part.text.trim(),
    };
    if (built.text === "" && subParts.length === 0) {
      problems.add(`${partAt} needs to say what it asks.`);
    }
    const marks = problems.whole(part.marks, `${partAt}'s marks`);
    if (marks !== null) {
      built.marks = marks;
    }
    const lines = problems.whole(part.answerLines, `${partAt}'s answer lines`, MAX_ANSWER_LINES);
    if (lines !== null) {
      built.answer_lines = lines;
    }
    if (subParts.length > 0) {
      built.parts = subParts;
    }
    return built;
  });

  const built: CanonicalQuestion = { number };
  const stem = optional(question.stem);
  if (stem !== undefined) {
    built.stem = stem;
  }
  const marks = problems.whole(question.marks, `${at}'s marks`);
  if (marks !== null) {
    built.marks = marks;
  }
  const lines = problems.whole(question.answerLines, `${at}'s answer lines`, MAX_ANSWER_LINES);
  if (lines !== null) {
    built.answer_lines = lines;
  }
  if (parts.length > 0) {
    built.parts = parts;
  }
  if (built.stem === undefined && parts.length === 0) {
    problems.add(`${at} needs a question or at least one part.`);
  }
  return built;
}

function buildSchemeQuestion(
  question: SchemeQuestionDraft,
  index: number,
  problems: Problems
): CanonicalMarkSchemeQuestion {
  const at = `Mark scheme ${question.number.trim() || String(index + 1)}`;
  const parts: CanonicalMarkSchemePart[] = question.parts.map((part) => {
    const partAt = `${at}, part ${part.label.trim() || "?"}`;
    const built: CanonicalMarkSchemePart = {
      label: problems.required(part.label, `${partAt} needs a label.`),
      answer: problems.required(part.answer, `${partAt} needs an answer.`),
    };
    const marks = problems.whole(part.marks, `${partAt}'s marks`);
    if (marks !== null) {
      built.marks = marks;
    }
    const notes = optional(part.notes);
    if (notes !== undefined) {
      built.notes = notes;
    }
    return built;
  });
  const built: CanonicalMarkSchemeQuestion = {
    number: problems.required(question.number, `${at} needs a number.`),
  };
  if (parts.length > 0) {
    built.parts = parts;
  }
  const answer = optional(question.answer);
  if (answer !== undefined) {
    built.answer = answer;
  }
  const notes = optional(question.notes);
  if (notes !== undefined) {
    built.notes = notes;
  }
  return built;
}

/** One question as the renderer takes it, or null while the draft is too incomplete to send. */
export function canonicalQuestion(question: QuestionDraft, index: number): CanonicalQuestion | null {
  const problems = new Problems();
  const built = buildQuestion(question, index, problems);
  return problems.all.length > 0 ? null : built;
}

/** One mark scheme entry as the renderer takes it, or null while the draft is incomplete. */
export function canonicalSchemeQuestion(
  question: SchemeQuestionDraft,
  index: number
): CanonicalMarkSchemeQuestion | null {
  const problems = new Problems();
  const built = buildSchemeQuestion(question, index, problems);
  return problems.all.length > 0 ? null : built;
}

function dropLines<T extends { answer_lines?: number | null }>(value: T): T {
  const copy = { ...value };
  delete copy.answer_lines;
  return copy;
}

/** The question as a mark scheme shows it: the same words, without the space to answer in. */
export function withoutAnswerLines(question: CanonicalQuestion): CanonicalQuestion {
  const stripped = dropLines(question);
  if (stripped.parts === undefined) {
    return stripped;
  }
  return {
    ...stripped,
    parts: stripped.parts.map((part) => {
      const outer = dropLines(part);
      return outer.parts === undefined ? outer : { ...outer, parts: outer.parts.map(dropLines) };
    }),
  };
}

/** What a question is worth: its own marks when it has them, else what its parts add up to. */
export function questionMarks(question: QuestionDraft): number | null {
  const own = Number(question.marks.trim());
  if (question.marks.trim() && Number.isInteger(own)) {
    return own;
  }
  let total = 0;
  let counted = false;
  for (const part of question.parts) {
    for (const value of [part.marks, ...part.parts.map((sub) => sub.marks)]) {
      const marks = Number(value.trim());
      if (value.trim() && Number.isInteger(marks)) {
        total += marks;
        counted = true;
      }
    }
  }
  return counted ? total : null;
}

/**
 * The draft as the canonical structure, built key by key: only the fields the typeset
 * service names are ever sent, and an empty one is left out rather than sent as null.
 */
export function buildPatch(draft: PaperDraft): Built {
  const problems = new Problems();
  const title = problems.required(draft.title, "Give the paper a title.");

  const questions: CanonicalQuestion[] = draft.questions.map((question, index) =>
    buildQuestion(question, index, problems)
  );

  const schemeQuestions: CanonicalMarkSchemeQuestion[] = draft.scheme.map((question, index) =>
    buildSchemeQuestion(question, index, problems)
  );

  const structure: CanonicalPaper = { title };
  const source = optional(draft.source);
  if (source !== undefined) {
    structure.source = source;
  }
  const board = optional(draft.board);
  if (board !== undefined) {
    structure.board = board;
  }
  const year = problems.whole(draft.year, "The year");
  if (year !== null) {
    structure.year = year;
  }
  const timeMinutes = problems.whole(draft.timeMinutes, "The time allowed");
  if (timeMinutes !== null) {
    structure.time_minutes = timeMinutes;
  }
  const totalMarks = problems.whole(draft.totalMarks, "The total marks");
  if (totalMarks !== null) {
    structure.total_marks = totalMarks;
  }
  const instructions = optional(draft.instructions);
  if (instructions !== undefined) {
    structure.instructions = instructions;
  }
  if (questions.length > 0) {
    structure.questions = questions;
  }

  if (problems.all.length > 0) {
    return { ok: false, problems: problems.all };
  }

  return {
    ok: true,
    patch: {
      title,
      source: source ?? null,
      board: board ?? null,
      year,
      time_minutes: timeMinutes,
      total_marks: totalMarks,
      instructions: instructions ?? null,
      structure,
      // The mark scheme takes the paper's title, so renaming the paper renames both PDFs.
      mark_scheme:
        schemeQuestions.length > 0 ? { title, questions: schemeQuestions } : null,
    },
  };
}
