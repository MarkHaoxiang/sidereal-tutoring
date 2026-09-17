import { feedbackTitle } from "@/lib/feedback";
import type { FeedbackListItem, HomeworkListItem, PlanListItem } from "@/lib/queries";
import type { FeedbackStatus, HomeworkStatus, PlanStatus } from "@/lib/schema";

export type ArtefactKind = "homework" | "feedback" | "plan";

/** Homework, feedback and study plans as one list — what a tutor thinks of as "work". */
export interface ArtefactSummary {
  id: string;
  kind: ArtefactKind;
  title: string;
  status: HomeworkStatus | FeedbackStatus | PlanStatus;
  created: string | null;
  student: { id: string; name: string } | null;
}

export function artefactPath(studentId: string, kind: ArtefactKind, id: string): string {
  const segment = kind === "plan" ? "plans" : kind;
  return `/students/${studentId}/${segment}/${id}`;
}

export function collectArtefacts(sources: {
  homework?: HomeworkListItem[];
  feedback?: FeedbackListItem[];
  plans?: PlanListItem[];
}): ArtefactSummary[] {
  return [
    ...(sources.homework ?? []).map((item) => ({
      id: item.id,
      kind: "homework" as const,
      title: item.title ?? "Untitled homework",
      status: item.status,
      created: item.date_created,
      student: item.student,
    })),
    ...(sources.feedback ?? []).map((item) => ({
      id: item.id,
      kind: "feedback" as const,
      title: feedbackTitle(item),
      status: item.status,
      created: item.date_created,
      student: item.student,
    })),
    ...(sources.plans ?? []).map((item) => ({
      id: item.id,
      kind: "plan" as const,
      title: item.title ?? "Untitled study plan",
      status: item.status,
      created: item.date_created,
      student: item.student,
    })),
  ].sort((a, b) => (b.created ?? "").localeCompare(a.created ?? ""));
}
