// Mirrors directus/schema/snapshot.yaml — collections, fields and relations here must
// change together with that file, never independently.

export type StudentStatus = "active" | "paused" | "archived";
export type SessionStatus = "scheduled" | "completed" | "cancelled";
export type DocumentKind = "transcript" | "web_page" | "question_bank" | "upload" | "scan";
export type DocumentStatus = "pending" | "processing" | "ready" | "failed";
export type HomeworkStatus = "draft" | "assigned" | "submitted" | "marked";
export type HomeworkFormat = "markdown" | "typst";
export type FeedbackStatus = "draft" | "sent";
export type PlanStatus = "draft" | "active" | "completed";
export type PaperStatus = "draft" | "reviewed" | "archived";
export type GenerationJobKind = "homework" | "feedback" | "plan" | "paper_extract";
export type GenerationJobStatus = "queued" | "running" | "succeeded" | "failed";

interface AuditFields {
  date_created: string | null;
  date_updated: string | null;
  user_created: string | DirectusUser | null;
  user_updated: string | DirectusUser | null;
}

// Directus's built-in users collection, referenced but not owned by this app.
export interface DirectusUser {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
}

export interface DirectusFile {
  id: string;
  filename_download: string;
}

export interface Student extends AuditFields {
  id: string;
  name: string;
  level: string | null;
  subjects: string[] | null;
  notes: string | null;
  tutor: string | DirectusUser | null;
  user: string | DirectusUser | null;
  status: StudentStatus;
}

export interface Session extends AuditFields {
  id: string;
  student: string | Student;
  tutor: string | DirectusUser | null;
  scheduled_at: string | null;
  duration_minutes: number | null;
  notes: string | null;
  status: SessionStatus;
}

// A scan's transcription: `documents.transcription` for a solutions scan and
// `homework.submission_transcription` for a hand-in, keyed by the paper's or homework's
// question numbers. Maths is Typst markup; `[?]` marks an unreadable span.
export type TranscriptionConfidence = "high" | "medium" | "low";

export interface TranscribedQuestion {
  number: string;
  text: string;
  confidence: TranscriptionConfidence;
  note?: string;
}

export interface Transcription {
  // `homework.submission_transcription` carries all of these, `model` and `usage` being what
  // the call cost; `documents.transcription` carries `questions` alone, and the whole of it is
  // the row's own `text`.
  text?: string;
  confidence?: TranscriptionConfidence;
  questions: TranscribedQuestion[];
  model?: string;
  usage?: Record<string, unknown>;
}

export interface Document extends AuditFields {
  id: string;
  title: string | null;
  kind: DocumentKind;
  source_url: string | null;
  file: string | DirectusFile | null;
  text: string | null;
  student: string | Student | null;
  session: string | Session | null;
  paper: string | Paper | null;
  transcription: Transcription | null;
  status: DocumentStatus;
  error: string | null;
  metadata: Record<string, unknown> | null;
  // Alias m2m field through the `document_topics` junction.
  topics: string[] | DocumentTopic[];
  // Alias m2m field through the `document_pages` junction.
  pages: string[] | DocumentPage[];
}

export interface Topic extends AuditFields {
  id: string;
  name: string;
  parent: string | Topic | null;
  description: string | null;
  sort: number | null;
  // Alias m2m fields through the three junctions below.
  documents: string[] | DocumentTopic[];
  questions: string[] | QuestionTopic[];
  homework: string[] | HomeworkTopic[];
}

// The canonical document structures, mirroring services/typeset/src/document.rs field for
// field. `papers.structure` is a CanonicalPaper and `papers.mark_scheme` a CanonicalMarkScheme;
// the typeset service's /render refuses any field not named here.
export type CanonicalAnswerKind =
  | "lines"
  | "box"
  | "multiple_choice"
  | "essay"
  | "grid"
  | "table"
  | "none";

export interface CanonicalAnswerOption {
  label?: string | null;
  text: string;
}

// `type` decides which of the other fields are read; the rest are ignored.
export interface CanonicalAnswer {
  type: CanonicalAnswerKind;
  lines?: number | null;
  options?: CanonicalAnswerOption[];
  height_mm?: number | null;
  rows?: number | null;
  cols?: number | null;
}

export interface CanonicalPassageBlock {
  type: "passage";
  title?: string | null;
  text: string;
}

// Points at a CanonicalPaper.passages entry, printed once at the start of the paper.
export interface CanonicalPassageRefBlock {
  type: "passage_ref";
  id: string;
}

export interface CanonicalCodeBlock {
  type: "code";
  language?: string | null;
  text: string;
}

export interface CanonicalTableBlock {
  type: "table";
  caption?: string | null;
  header?: string[] | null;
  rows?: string[][];
}

// `asset` names one of the render request's assets, never a path: a file id and its suffix.
export interface CanonicalFigureBlock {
  type: "figure";
  asset: string;
  caption?: string | null;
  width_mm?: number | null;
}

export type CanonicalBlock =
  | CanonicalPassageBlock
  | CanonicalPassageRefBlock
  | CanonicalCodeBlock
  | CanonicalTableBlock
  | CanonicalFigureBlock;

export interface CanonicalPassage {
  id: string;
  title?: string | null;
  text: string;
}

export interface CanonicalPart {
  label: string;
  text: string;
  marks?: number | null;
  /** The deprecated spelling of `{ type: "lines" }`. A node carries this or `answer`, never both. */
  answer_lines?: number | null;
  answer?: CanonicalAnswer | null;
  blocks?: CanonicalBlock[];
  // Parts nest one level, `(a)` then `(i)`, so a part of a part carries none of its own.
  parts?: CanonicalPart[];
}

export interface CanonicalQuestion {
  number: string;
  stem?: string | null;
  marks?: number | null;
  parts?: CanonicalPart[];
  /** The deprecated spelling of `{ type: "lines" }`. A node carries this or `answer`, never both. */
  answer_lines?: number | null;
  answer?: CanonicalAnswer | null;
  blocks?: CanonicalBlock[];
}

// A run of questions under one heading; `choose` is how many of them the student answers.
export interface CanonicalSection {
  title?: string | null;
  instructions?: string | null;
  choose?: number | null;
  questions?: CanonicalQuestion[];
}

export interface CanonicalPaper {
  title: string;
  source?: string | null;
  board?: string | null;
  year?: number | null;
  time_minutes?: number | null;
  total_marks?: number | null;
  instructions?: string | null;
  questions?: CanonicalQuestion[];
  sections?: CanonicalSection[];
  passages?: CanonicalPassage[];
}

export interface CanonicalMarkSchemePart {
  label: string;
  answer: string;
  marks?: number | null;
  notes?: string | null;
  blocks?: CanonicalBlock[];
}

export interface CanonicalMarkSchemeQuestion {
  number: string;
  parts?: CanonicalMarkSchemePart[];
  answer?: string | null;
  notes?: string | null;
  blocks?: CanonicalBlock[];
}

export interface CanonicalMarkScheme {
  title: string;
  questions?: CanonicalMarkSchemeQuestion[];
}

export interface Question extends AuditFields {
  id: string;
  text: string;
  answer: string | null;
  subject: string | null;
  topic: string | null;
  difficulty: number | null;
  document: string | Document | null;
  paper: string | Paper | null;
  number: string | null;
  marks: number | null;
  parts: CanonicalPart[] | null;
  answer_lines: number | null;
  mark_scheme: CanonicalMarkSchemeQuestion | null;
  // Alias m2m field through the `homework_questions` junction.
  homework: string[] | HomeworkQuestion[];
  // Alias m2m field through the `question_topics` junction.
  topics: string[] | QuestionTopic[];
}

// Written by `UsageTally.provenance()`: present only for the calls it actually priced.
export interface GenerationUsage {
  calls: number;
  cost_usd?: number;
}

// A paper's own field, appended to by `extract_paper_mark_scheme` alone: what a re-run
// read, and what it cost. `usage` is null when its backend recorded no call.
export interface GenerationRerun {
  kind: string;
  document: string;
  model: string;
  at: string;
  usage: GenerationUsage | null;
}

// Written by `sidereal_generate.jobs`: ids as strings, `questions` on homework only.
export interface GenerationProvenance {
  job: string;
  model: string;
  documents: string[];
  questions?: string[];
  /** Written when the artefact was filed but something after it did not run. */
  warning?: string;
  /** What this run's calls cost, filed only when every one of them priced. */
  usage?: GenerationUsage;
  /** The extraction's `usage` summed with every rerun's, once there has been one. */
  usage_total?: GenerationUsage;
  /** A paper's own field: the document its mark scheme was last read from. */
  mark_scheme_document?: string;
  /** A paper's own field: every later read of its mark scheme, oldest first. */
  reruns?: GenerationRerun[];
}

export interface Paper extends AuditFields {
  id: string;
  title: string;
  source: string | null;
  board: string | null;
  year: number | null;
  time_minutes: number | null;
  total_marks: number | null;
  instructions: string | null;
  status: PaperStatus;
  document: string | Document | null;
  rendered_pdf: string | DirectusFile | null;
  mark_scheme_pdf: string | DirectusFile | null;
  structure: CanonicalPaper | null;
  mark_scheme: CanonicalMarkScheme | null;
  generated_from: GenerationProvenance | null;
}

export interface Homework extends AuditFields {
  id: string;
  student: string | Student;
  session: string | Session | null;
  title: string | null;
  content: string | null;
  format: HomeworkFormat;
  pdf: string | DirectusFile | null;
  compile_error: string | null;
  due_on: string | null;
  status: HomeworkStatus;
  submission: string | null;
  submission_file: string | DirectusFile | null;
  submission_transcription: Transcription | null;
  submitted_at: string | null;
  generated_from: GenerationProvenance | null;
  // Alias m2m field through the `homework_questions` junction.
  questions: string[] | HomeworkQuestion[];
  // Alias m2m field through the `homework_topics` junction.
  topics: string[] | HomeworkTopic[];
}

export interface Feedback extends AuditFields {
  id: string;
  student: string | Student;
  session: string | Session | null;
  content: string | null;
  status: FeedbackStatus;
  generated_from: GenerationProvenance | null;
}

export interface Plan extends AuditFields {
  id: string;
  student: string | Student;
  title: string | null;
  content: string | null;
  period_start: string | null;
  period_end: string | null;
  status: PlanStatus;
  generated_from: GenerationProvenance | null;
}

export interface GenerationJob extends AuditFields {
  id: string;
  kind: GenerationJobKind;
  student: string | Student | null;
  status: GenerationJobStatus;
  input: Record<string, unknown> | null;
  output_collection: string | null;
  output_id: string | null;
  error: string | null;
  model: string | null;
}

export interface HomeworkQuestion extends AuditFields {
  id: string;
  homework: string | Homework;
  question: string | Question;
  sort: number | null;
}

export interface DocumentPage extends AuditFields {
  id: string;
  document: string | Document;
  file: string | DirectusFile;
  sort: number | null;
}

export interface DocumentTopic extends AuditFields {
  id: string;
  document: string | Document;
  topic: string | Topic;
  sort: number | null;
}

export interface QuestionTopic extends AuditFields {
  id: string;
  question: string | Question;
  topic: string | Topic;
  sort: number | null;
}

export interface HomeworkTopic extends AuditFields {
  id: string;
  homework: string | Homework;
  topic: string | Topic;
  sort: number | null;
}

export interface Schema {
  // Declared so the SDK can expand `user_created`; the snapshot does not own this collection.
  directus_users: DirectusUser[];
  students: Student[];
  sessions: Session[];
  documents: Document[];
  papers: Paper[];
  questions: Question[];
  homework: Homework[];
  feedback: Feedback[];
  plans: Plan[];
  generation_jobs: GenerationJob[];
  topics: Topic[];
  homework_questions: HomeworkQuestion[];
  document_topics: DocumentTopic[];
  document_pages: DocumentPage[];
  question_topics: QuestionTopic[];
  homework_topics: HomeworkTopic[];
}
