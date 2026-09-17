import type { PaperDetail, PaperPatch } from "@/lib/queries";
import type {
  CanonicalAnswer,
  CanonicalAnswerKind,
  CanonicalBlock,
  CanonicalMarkScheme,
  CanonicalMarkSchemePart,
  CanonicalMarkSchemeQuestion,
  CanonicalPaper,
  CanonicalPart,
  CanonicalPassage,
  CanonicalQuestion,
  CanonicalSection,
} from "@/lib/schema";

// The renderer's caps, mirroring the module constants in sidereal_core.canonical.
export const MAX_ANSWER_LINES = 60;
export const MAX_ANSWER_HEIGHT_MM = 250;
export const MAX_ANSWER_OPTIONS = 26;
export const MAX_GRID_ROWS = 40;
export const MAX_GRID_COLS = 26;
export const MAX_TABLE_ROWS = 40;
export const MAX_TABLE_COLS = 12;
export const MAX_FIGURE_WIDTH_MM = 165;

export const ANSWER_KINDS: { id: CanonicalAnswerKind; label: string }[] = [
  { id: "lines", label: "Lines" },
  { id: "box", label: "Box" },
  { id: "multiple_choice", label: "Multiple choice" },
  { id: "essay", label: "Essay" },
  { id: "grid", label: "Grid" },
  { id: "table", label: "Table" },
  { id: "none", label: "None" },
];

// What a tutor calls each block: an `extract` is set here, a `passage` is one of the
// paper's own, printed once at the front and pointed at from here.
export const BLOCK_KINDS: { id: BlockDraft["type"]; label: string }[] = [
  { id: "passage", label: "Extract" },
  { id: "passage_ref", label: "Passage" },
  { id: "code", label: "Code" },
  { id: "table", label: "Table" },
  { id: "figure", label: "Figure" },
];

// Every number is held as the text in its input, so a half-typed value is still a value.
// `key` is React's, never Directus's: the structure it is stripped from has no ids.
export interface AnswerOptionDraft {
  key: string;
  label: string;
  text: string;
}

export interface AnswerDraft {
  type: CanonicalAnswerKind;
  lines: string;
  heightMm: string;
  rows: string;
  cols: string;
  options: AnswerOptionDraft[];
}

export type BlockDraft =
  | { key: string; type: "passage"; title: string; text: string }
  | { key: string; type: "passage_ref"; id: string }
  | { key: string; type: "code"; language: string; text: string }
  | { key: string; type: "table"; caption: string; header: string[] | null; rows: string[][] }
  | { key: string; type: "figure"; asset: string; caption: string; widthMm: string };

export interface SubPartDraft {
  key: string;
  label: string;
  text: string;
  marks: string;
  /** The deprecated spelling, kept as it was read so an untouched paper saves unchanged. */
  answerLines: string;
  answer: AnswerDraft | null;
  blocks: BlockDraft[];
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
  answer: AnswerDraft | null;
  blocks: BlockDraft[];
  parts: PartDraft[];
}

export interface SectionDraft {
  key: string;
  title: string;
  instructions: string;
  choose: string;
  questions: QuestionDraft[];
}

export interface PassageDraft {
  key: string;
  id: string;
  title: string;
  text: string;
}

export interface SchemePartDraft {
  key: string;
  label: string;
  answer: string;
  marks: string;
  notes: string;
  blocks: BlockDraft[];
}

export interface SchemeQuestionDraft {
  key: string;
  number: string;
  answer: string;
  notes: string;
  blocks: BlockDraft[];
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
  sections: SectionDraft[];
  passages: PassageDraft[];
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

function answerDraft(answer: CanonicalAnswer | null | undefined): AnswerDraft | null {
  if (!answer) {
    return null;
  }
  return {
    type: answer.type,
    lines: num(answer.lines),
    heightMm: num(answer.height_mm),
    rows: num(answer.rows),
    cols: num(answer.cols),
    options: (answer.options ?? []).map((option) => ({
      key: key(),
      label: text(option.label),
      text: option.text,
    })),
  };
}

function blockDraft(block: CanonicalBlock): BlockDraft {
  switch (block.type) {
    case "passage":
      return { key: key(), type: "passage", title: text(block.title), text: block.text };
    case "passage_ref":
      return { key: key(), type: "passage_ref", id: block.id };
    case "code":
      return { key: key(), type: "code", language: text(block.language), text: block.text };
    case "table":
      return {
        key: key(),
        type: "table",
        caption: text(block.caption),
        header: block.header ? [...block.header] : null,
        rows: (block.rows ?? []).map((row) => [...row]),
      };
    case "figure":
      return {
        key: key(),
        type: "figure",
        asset: block.asset,
        caption: text(block.caption),
        widthMm: num(block.width_mm),
      };
  }
}

function subPartDraft(part: CanonicalPart): SubPartDraft {
  return {
    key: key(),
    label: part.label,
    text: part.text,
    marks: num(part.marks),
    answerLines: num(part.answer_lines),
    answer: answerDraft(part.answer),
    blocks: (part.blocks ?? []).map(blockDraft),
  };
}

function questionDraft(question: CanonicalQuestion): QuestionDraft {
  return {
    key: key(),
    number: question.number,
    stem: text(question.stem),
    marks: num(question.marks),
    answerLines: num(question.answer_lines),
    answer: answerDraft(question.answer),
    blocks: (question.blocks ?? []).map(blockDraft),
    parts: (question.parts ?? []).map((part) => ({
      ...subPartDraft(part),
      parts: (part.parts ?? []).map(subPartDraft),
    })),
  };
}

export function emptyAnswer(type: CanonicalAnswerKind): AnswerDraft {
  return { type, lines: "", heightMm: "", rows: "", cols: "", options: [] };
}

export function emptyAnswerOption(): AnswerOptionDraft {
  return { key: key(), label: "", text: "" };
}

export function emptyBlock(type: BlockDraft["type"]): BlockDraft {
  switch (type) {
    case "passage":
      return { key: key(), type, title: "", text: "" };
    case "passage_ref":
      return { key: key(), type, id: "" };
    case "code":
      return { key: key(), type, language: "", text: "" };
    case "table":
      return { key: key(), type, caption: "", header: ["", ""], rows: [["", ""]] };
    case "figure":
      return { key: key(), type, asset: "", caption: "", widthMm: "" };
  }
}

export function emptySubPart(): SubPartDraft {
  return { key: key(), label: "", text: "", marks: "", answerLines: "", answer: null, blocks: [] };
}

export function emptyPart(): PartDraft {
  return { ...emptySubPart(), parts: [] };
}

export function emptyQuestion(): QuestionDraft {
  return {
    key: key(),
    number: "",
    stem: "",
    marks: "",
    answerLines: "",
    answer: null,
    blocks: [],
    parts: [],
  };
}

export function emptySection(): SectionDraft {
  return { key: key(), title: "", instructions: "", choose: "", questions: [] };
}

export function emptyPassage(): PassageDraft {
  return { key: key(), id: "", title: "", text: "" };
}

export function emptySchemePart(): SchemePartDraft {
  return { key: key(), label: "", answer: "", marks: "", notes: "", blocks: [] };
}

export function emptySchemeQuestion(): SchemeQuestionDraft {
  return { key: key(), number: "", answer: "", notes: "", blocks: [], parts: [] };
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
    questions: (structure?.questions ?? []).map(questionDraft),
    sections: (structure?.sections ?? []).map((section) => ({
      key: key(),
      title: text(section.title),
      instructions: text(section.instructions),
      choose: num(section.choose),
      questions: (section.questions ?? []).map(questionDraft),
    })),
    passages: (structure?.passages ?? []).map((passage) => ({
      key: key(),
      id: passage.id,
      title: text(passage.title),
      text: passage.text,
    })),
    scheme: (scheme?.questions ?? []).map((question) => ({
      key: key(),
      number: question.number,
      answer: text(question.answer),
      notes: text(question.notes),
      blocks: (question.blocks ?? []).map(blockDraft),
      parts: (question.parts ?? []).map((part) => ({
        key: key(),
        label: part.label,
        answer: part.answer,
        marks: num(part.marks),
        notes: text(part.notes),
        blocks: (part.blocks ?? []).map(blockDraft),
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

export type Built = { ok: true; patch: PaperPatch } | { ok: false; problems: string[] };

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

function buildAnswer(answer: AnswerDraft, at: string, problems: Problems): CanonicalAnswer {
  const built: CanonicalAnswer = { type: answer.type };
  const lines = problems.whole(answer.lines, `${at}'s answer lines`, MAX_ANSWER_LINES);
  if (lines !== null) {
    built.lines = lines;
  }
  const height = problems.whole(answer.heightMm, `${at}'s answer height`, MAX_ANSWER_HEIGHT_MM);
  if (height !== null) {
    built.height_mm = height;
  }
  const maxRows = answer.type === "table" ? MAX_TABLE_ROWS : MAX_GRID_ROWS;
  const maxCols = answer.type === "table" ? MAX_TABLE_COLS : MAX_GRID_COLS;
  const rows = problems.whole(answer.rows, `${at}'s answer rows`, maxRows);
  if (rows !== null) {
    built.rows = rows;
  }
  const cols = problems.whole(answer.cols, `${at}'s answer columns`, maxCols);
  if (cols !== null) {
    built.cols = cols;
  }
  if (answer.options.length > 0) {
    built.options = answer.options.map((option) => {
      const one: { label?: string; text: string } = {
        text: problems.required(option.text, `${at} has a choice with nothing in it.`),
      };
      const label = optional(option.label);
      if (label !== undefined) {
        one.label = label;
      }
      return one;
    });
  }
  if (answer.type === "multiple_choice" && answer.options.length === 0) {
    problems.add(`${at} needs at least one choice.`);
  }
  if (answer.options.length > MAX_ANSWER_OPTIONS) {
    problems.add(`${at} is over ${String(MAX_ANSWER_OPTIONS)} choices.`);
  }
  if ((answer.type === "grid" || answer.type === "table") && (rows === null || cols === null)) {
    problems.add(`${at} needs both rows and columns.`);
  }
  return built;
}

function buildBlock(block: BlockDraft, at: string, problems: Problems): CanonicalBlock {
  switch (block.type) {
    case "passage": {
      const built: CanonicalBlock = {
        type: "passage",
        text: problems.required(block.text, `${at} has an empty passage.`),
      };
      const title = optional(block.title);
      if (title !== undefined) {
        built.title = title;
      }
      return built;
    }
    case "passage_ref":
      return {
        type: "passage_ref",
        id: problems.required(block.id, `${at} has a passage reference with no passage.`),
      };
    case "code": {
      const built: CanonicalBlock = {
        type: "code",
        text: problems.required(block.text, `${at} has an empty code block.`),
      };
      const language = optional(block.language);
      if (language !== undefined) {
        built.language = language;
      }
      return built;
    }
    case "table": {
      const built: CanonicalBlock = { type: "table" };
      const caption = optional(block.caption);
      if (caption !== undefined) {
        built.caption = caption;
      }
      if (block.header !== null) {
        built.header = [...block.header];
      }
      if (block.rows.length > 0) {
        built.rows = block.rows.map((row) => [...row]);
      }
      const columns = block.header?.length ?? block.rows[0]?.length ?? 0;
      if (columns === 0) {
        problems.add(`${at} has a table with no columns.`);
      } else if (columns > MAX_TABLE_COLS) {
        problems.add(`${at} has a table over ${String(MAX_TABLE_COLS)} columns wide.`);
      }
      if (block.rows.length > MAX_TABLE_ROWS) {
        problems.add(`${at} has a table over ${String(MAX_TABLE_ROWS)} rows long.`);
      }
      if (block.rows.some((row) => row.length !== columns)) {
        problems.add(`${at} has a table row with the wrong number of cells.`);
      }
      return built;
    }
    case "figure": {
      const built: CanonicalBlock = {
        type: "figure",
        asset: problems.required(block.asset, `${at} has a figure with no image.`),
      };
      const caption = optional(block.caption);
      if (caption !== undefined) {
        built.caption = caption;
      }
      const width = problems.whole(block.widthMm, `${at}'s figure width`, MAX_FIGURE_WIDTH_MM);
      if (width !== null) {
        built.width_mm = width;
      }
      return built;
    }
  }
}

function buildBlocks(blocks: BlockDraft[], at: string, problems: Problems): CanonicalBlock[] {
  return blocks.map((block) => buildBlock(block, at, problems));
}

/** The answer space and the blocks every node carries, written onto the node being built. */
function addNodeFields(
  built: {
    answer_lines?: number | null;
    answer?: CanonicalAnswer | null;
    blocks?: CanonicalBlock[];
  },
  draft: { answerLines: string; answer: AnswerDraft | null; blocks: BlockDraft[] },
  at: string,
  problems: Problems
): void {
  const blocks = buildBlocks(draft.blocks, at, problems);
  if (blocks.length > 0) {
    built.blocks = blocks;
  }
  if (draft.answer !== null) {
    built.answer = buildAnswer(draft.answer, at, problems);
    if (draft.answerLines.trim()) {
      problems.add(`${at} carries both an answer and the older answer lines.`);
    }
    return;
  }
  const lines = problems.whole(draft.answerLines, `${at}'s answer lines`, MAX_ANSWER_LINES);
  if (lines !== null) {
    built.answer_lines = lines;
  }
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
        label: sub.label.trim(),
        text: problems.required(sub.text, `${subAt} needs to say what it asks.`),
      };
      const subMarks = problems.whole(sub.marks, `${subAt}'s marks`);
      if (subMarks !== null) {
        builtSub.marks = subMarks;
      }
      addNodeFields(builtSub, sub, subAt, problems);
      return builtSub;
    });

    // A part that only groups sub-parts asks nothing itself, so its text may be empty, and
    // a paper that numbers its questions rather than its parts leaves the label empty too.
    const built: CanonicalPart = {
      label: part.label.trim(),
      text: part.text.trim(),
    };
    if (built.text === "" && subParts.length === 0) {
      problems.add(`${partAt} needs to say what it asks.`);
    }
    const marks = problems.whole(part.marks, `${partAt}'s marks`);
    if (marks !== null) {
      built.marks = marks;
    }
    addNodeFields(built, part, partAt, problems);
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
  addNodeFields(built, question, at, problems);
  if (parts.length > 0) {
    built.parts = parts;
  }
  if (built.stem === undefined && parts.length === 0 && question.blocks.length === 0) {
    problems.add(`${at} needs a question, a block or at least one part.`);
  }
  return built;
}

function buildSection(
  section: SectionDraft,
  index: number,
  problems: Problems
): CanonicalSection {
  const at = section.title.trim() || `Section ${String(index + 1)}`;
  const built: CanonicalSection = {};
  const title = optional(section.title);
  if (title !== undefined) {
    built.title = title;
  }
  const instructions = optional(section.instructions);
  if (instructions !== undefined) {
    built.instructions = instructions;
  }
  const choose = problems.whole(section.choose, `${at}'s "answer this many"`);
  if (choose !== null) {
    built.choose = choose;
    if (choose < 1 || choose > section.questions.length) {
      problems.add(
        `${at} offers ${String(section.questions.length)} questions, so ${String(choose)} cannot be chosen.`
      );
    }
  }
  const questions = section.questions.map((question, position) =>
    buildQuestion(question, position, problems)
  );
  if (questions.length > 0) {
    built.questions = questions;
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
      label: part.label.trim(),
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
    const blocks = buildBlocks(part.blocks, partAt, problems);
    if (blocks.length > 0) {
      built.blocks = blocks;
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
  const blocks = buildBlocks(question.blocks, at, problems);
  if (blocks.length > 0) {
    built.blocks = blocks;
  }
  return built;
}

/** One question as the renderer takes it, or null while the draft is too incomplete to send. */
export function canonicalQuestion(question: QuestionDraft, index: number): CanonicalQuestion | null {
  const problems = new Problems();
  const built = buildQuestion(question, index, problems);
  return problems.all.length > 0 ? null : built;
}

function inlined(blocks: CanonicalBlock[] | undefined, passages: PassageDraft[]): CanonicalBlock[] {
  return (blocks ?? []).flatMap((block) => {
    if (block.type !== "passage_ref") {
      return [block];
    }
    const passage = passages.find((entry) => entry.id.trim() === block.id);
    if (passage === undefined) {
      return [];
    }
    const built: CanonicalBlock = { type: "passage", text: passage.text };
    const title = optional(passage.title);
    if (title !== undefined) {
      built.title = title;
    }
    return [built];
  });
}

function withPassages<T extends { blocks?: CanonicalBlock[] }>(
  node: T,
  passages: PassageDraft[]
): T {
  const blocks = inlined(node.blocks, passages);
  return blocks.length > 0 ? { ...node, blocks } : { ...node, blocks: undefined };
}

/**
 * One question as a card previews it. A fragment is rendered on its own, with no paper to
 * hold the passages, so a `passage_ref` is set as the passage it points at.
 */
export function fragmentQuestion(
  question: QuestionDraft,
  index: number,
  passages: PassageDraft[]
): CanonicalQuestion | null {
  const built = canonicalQuestion(question, index);
  if (built === null) {
    return null;
  }
  const whole = withPassages(built, passages);
  if (whole.parts === undefined) {
    return whole;
  }
  return {
    ...whole,
    parts: whole.parts.map((part) => {
      const outer = withPassages(part, passages);
      return outer.parts === undefined
        ? outer
        : { ...outer, parts: outer.parts.map((sub) => withPassages(sub, passages)) };
    }),
  };
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

function dropAnswer<T extends { answer_lines?: number | null; answer?: CanonicalAnswer | null }>(
  value: T
): T {
  const copy = { ...value };
  delete copy.answer_lines;
  delete copy.answer;
  return copy;
}

/** The question as a mark scheme shows it: the same words, without the space to answer in. */
export function withoutAnswerSpace(question: CanonicalQuestion): CanonicalQuestion {
  const stripped = dropAnswer(question);
  if (stripped.parts === undefined) {
    return stripped;
  }
  return {
    ...stripped,
    parts: stripped.parts.map((part) => {
      const outer = dropAnswer(part);
      return outer.parts === undefined ? outer : { ...outer, parts: outer.parts.map(dropAnswer) };
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

/** Every question the paper asks, loose ones first, in the order they print. */
export function allQuestions(draft: PaperDraft): QuestionDraft[] {
  return [...draft.questions, ...draft.sections.flatMap((section) => section.questions)];
}

/** The same, for a paper as it is stored: a sectioned paper's questions are in its sections. */
export function structureQuestions(structure: CanonicalPaper | null): CanonicalQuestion[] {
  return [
    ...(structure?.questions ?? []),
    ...(structure?.sections ?? []).flatMap((section) => section.questions ?? []),
  ];
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

  const sections: CanonicalSection[] = draft.sections.map((section, index) =>
    buildSection(section, index, problems)
  );

  const passages: CanonicalPassage[] = draft.passages.map((passage, index) => {
    const at = `Passage ${passage.id.trim() || String(index + 1)}`;
    const built: CanonicalPassage = {
      id: problems.required(passage.id, `${at} needs a name to be referred to by.`),
      text: problems.required(passage.text, `${at} needs some text.`),
    };
    const passageTitle = optional(passage.title);
    if (passageTitle !== undefined) {
      built.title = passageTitle;
    }
    return built;
  });

  const named = new Set(passages.map((passage) => passage.id));
  for (const question of allQuestions(draft)) {
    for (const block of question.blocks) {
      if (block.type === "passage_ref" && block.id.trim() && !named.has(block.id.trim())) {
        problems.add(
          `Question ${question.number.trim()} points at "${block.id.trim()}", ` +
            "which is not a passage on this paper."
        );
      }
    }
  }

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
  if (sections.length > 0) {
    structure.sections = sections;
  }
  if (passages.length > 0) {
    structure.passages = passages;
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
      mark_scheme: schemeQuestions.length > 0 ? { title, questions: schemeQuestions } : null,
    },
  };
}
