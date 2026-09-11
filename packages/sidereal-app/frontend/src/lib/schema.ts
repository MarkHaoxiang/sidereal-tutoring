// Mirrors directus/schema/snapshot.yaml — collections, fields and relations here must
// change together with that file, never independently.

export type StudentStatus = "active" | "paused" | "archived";
export type SessionStatus = "scheduled" | "completed" | "cancelled";
export type DocumentKind = "transcript" | "web_page" | "question_bank" | "upload";
export type DocumentStatus = "pending" | "processing" | "ready" | "failed";
export type HomeworkStatus = "draft" | "assigned" | "submitted" | "marked";
export type FeedbackStatus = "draft" | "sent";
export type PlanStatus = "draft" | "active" | "completed";
export type GenerationJobKind = "homework" | "feedback" | "plan";
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

export interface Document extends AuditFields {
  id: string;
  title: string | null;
  kind: DocumentKind;
  source_url: string | null;
  file: string | DirectusFile | null;
  text: string | null;
  student: string | Student | null;
  session: string | Session | null;
  status: DocumentStatus;
  error: string | null;
  metadata: Record<string, unknown> | null;
}

export interface Question extends AuditFields {
  id: string;
  text: string;
  answer: string | null;
  subject: string | null;
  topic: string | null;
  difficulty: number | null;
  document: string | Document | null;
  // Alias m2m field through the `homework_questions` junction.
  homework: string[] | HomeworkQuestion[];
}

// Written by `sidereal_generate.jobs`: ids as strings, `questions` on homework only.
export interface GenerationProvenance {
  job: string;
  model: string;
  documents: string[];
  questions?: string[];
}

export interface Homework extends AuditFields {
  id: string;
  student: string | Student;
  session: string | Session | null;
  title: string | null;
  content: string | null;
  due_on: string | null;
  status: HomeworkStatus;
  generated_from: GenerationProvenance | null;
  // Alias m2m field through the `homework_questions` junction.
  questions: string[] | HomeworkQuestion[];
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

export interface Schema {
  students: Student[];
  sessions: Session[];
  documents: Document[];
  questions: Question[];
  homework: Homework[];
  feedback: Feedback[];
  plans: Plan[];
  generation_jobs: GenerationJob[];
  homework_questions: HomeworkQuestion[];
}
