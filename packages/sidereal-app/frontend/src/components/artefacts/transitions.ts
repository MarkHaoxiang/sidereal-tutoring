import type { FeedbackStatus, HomeworkStatus, PlanStatus } from "@/lib/schema";

export interface Transition<TStatus> {
  next: TStatus;
  label: string;
  /** What the toast says once the step is taken. */
  done: string;
}

// Only the step a tutor may take from where they are — a status is never a free choice.
// `submitted` has no entry: marking is the step, and the marking panel's own button takes it.
export const HOMEWORK_NEXT: Partial<Record<HomeworkStatus, Transition<HomeworkStatus>>> = {
  draft: { next: "assigned", label: "Assign", done: "Assigned" },
  assigned: { next: "submitted", label: "Mark handed in", done: "Handed in" },
};

export const FEEDBACK_NEXT: Partial<Record<FeedbackStatus, Transition<FeedbackStatus>>> = {
  draft: { next: "sent", label: "Mark sent", done: "Sent" },
};

export const PLAN_NEXT: Partial<Record<PlanStatus, Transition<PlanStatus>>> = {
  draft: { next: "active", label: "Mark active", done: "Active" },
  active: { next: "completed", label: "Mark completed", done: "Completed" },
};
