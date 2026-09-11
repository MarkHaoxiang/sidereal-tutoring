import type { FeedbackStatus, HomeworkStatus, PlanStatus } from "@/lib/schema";

export interface Transition<TStatus> {
  next: TStatus;
  label: string;
}

// Only the step a tutor may take from where they are — a status is never a free choice.
export const HOMEWORK_NEXT: Partial<Record<HomeworkStatus, Transition<HomeworkStatus>>> = {
  draft: { next: "assigned", label: "Mark as assigned" },
  assigned: { next: "submitted", label: "Mark as submitted" },
  submitted: { next: "marked", label: "Mark as marked" },
};

export const FEEDBACK_NEXT: Partial<Record<FeedbackStatus, Transition<FeedbackStatus>>> = {
  draft: { next: "sent", label: "Mark as sent" },
};

export const PLAN_NEXT: Partial<Record<PlanStatus, Transition<PlanStatus>>> = {
  draft: { next: "active", label: "Mark as active" },
  active: { next: "completed", label: "Mark as completed" },
};
