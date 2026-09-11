import type {
  DocumentKind,
  DocumentStatus,
  FeedbackStatus,
  GenerationJobKind,
  GenerationJobStatus,
  HomeworkStatus,
  PlanStatus,
  SessionStatus,
  StudentStatus,
} from "@/lib/schema";

// Every status and kind token the domain has, in one union: the Record below must
// cover it, so a token added to schema.ts without a label here is a type error.
export type StatusToken =
  | StudentStatus
  | SessionStatus
  | DocumentKind
  | DocumentStatus
  | HomeworkStatus
  | FeedbackStatus
  | PlanStatus
  | GenerationJobKind
  | GenerationJobStatus;

export type StatusTone = "muted" | "accent" | "success" | "danger" | "warning";

export const STATUS_TOKENS: Record<StatusToken, { label: string; tone: StatusTone }> = {
  active: { label: "Active", tone: "accent" },
  paused: { label: "Paused", tone: "muted" },
  archived: { label: "Archived", tone: "muted" },
  scheduled: { label: "Scheduled", tone: "accent" },
  completed: { label: "Completed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "danger" },
  transcript: { label: "Transcript", tone: "muted" },
  web_page: { label: "Web page", tone: "muted" },
  question_bank: { label: "Question bank", tone: "muted" },
  upload: { label: "Upload", tone: "muted" },
  pending: { label: "Waiting", tone: "muted" },
  processing: { label: "Processing", tone: "accent" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  draft: { label: "Draft", tone: "muted" },
  assigned: { label: "Assigned", tone: "accent" },
  submitted: { label: "Submitted", tone: "warning" },
  marked: { label: "Marked", tone: "success" },
  sent: { label: "Sent", tone: "success" },
  queued: { label: "Queued", tone: "muted" },
  running: { label: "Generating", tone: "accent" },
  succeeded: { label: "Done", tone: "success" },
  homework: { label: "Homework", tone: "muted" },
  feedback: { label: "Feedback", tone: "muted" },
  plan: { label: "Study plan", tone: "muted" },
};
