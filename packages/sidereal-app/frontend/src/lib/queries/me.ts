import { readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { directus } from "@/lib/directus";

// The student view's own data layer. Every request names the fields the Student policy
// grants and nothing else: `students.notes`, `sessions.notes`, `homework.generated_from`
// and `questions.answer` are the tutor's, and asking for any of them is a 403 for a
// student, not a blank. The row filters are Directus's, so no hook here passes a student
// id: a student's token can only ever reach their own rows.

export const meKeys = {
  all: ["me"] as const,
  student: ["me", "student"] as const,
  homework: ["me", "homework"] as const,
  homeworkDetail: (id: string) => ["me", "homework", id] as const,
  feedback: ["me", "feedback"] as const,
  feedbackDetail: (id: string) => ["me", "feedback", id] as const,
  plans: ["me", "plans"] as const,
  sessions: ["me", "sessions"] as const,
};

async function fetchMyStudent() {
  const rows = await directus.request(
    readItems("students", {
      fields: ["id", "name", "level", "subjects", "status"],
      limit: 1,
    })
  );
  return rows[0] ?? null;
}

function fetchMyHomeworkList() {
  return directus.request(
    readItems("homework", {
      fields: ["id", "title", "due_on", "status", "submitted_at", "date_created"],
      sort: ["-date_created"],
      limit: -1,
    })
  );
}

function fetchMyHomework(id: string) {
  return directus.request(
    readItem("homework", id, {
      fields: [
        "id",
        "title",
        "content",
        "due_on",
        "status",
        "submission",
        "submitted_at",
        "date_created",
        { questions: ["id", "sort", { question: ["id", "text"] }] },
      ],
    })
  );
}

function fetchMyFeedbackList() {
  return directus.request(
    readItems("feedback", {
      fields: ["id", "content", "status", "date_created"],
      filter: { status: { _eq: "sent" } },
      sort: ["-date_created"],
      limit: -1,
    })
  );
}

function fetchMyFeedback(id: string) {
  return directus.request(
    readItem("feedback", id, {
      fields: ["id", "content", "status", "date_created"],
    })
  );
}

// Plans are few and short, and both /me and /me/plan want their content, so one query
// carries the lot rather than a list plus a detail fetch.
function fetchMyPlans() {
  return directus.request(
    readItems("plans", {
      fields: ["id", "title", "content", "period_start", "period_end", "status", "date_created"],
      sort: ["-date_created"],
      limit: -1,
    })
  );
}

function fetchMySessions() {
  return directus.request(
    readItems("sessions", {
      fields: ["id", "scheduled_at", "duration_minutes", "status"],
      sort: ["scheduled_at"],
      limit: -1,
    })
  );
}

export type MyStudent = Awaited<ReturnType<typeof fetchMyStudent>>;
export type MyHomeworkListItem = Awaited<ReturnType<typeof fetchMyHomeworkList>>[number];
export type MyHomework = Awaited<ReturnType<typeof fetchMyHomework>>;
export type MyFeedbackItem = Awaited<ReturnType<typeof fetchMyFeedbackList>>[number];
export type MyPlan = Awaited<ReturnType<typeof fetchMyPlans>>[number];
export type MySession = Awaited<ReturnType<typeof fetchMySessions>>[number];

export function useMyStudent() {
  return useQuery({ queryKey: meKeys.student, queryFn: fetchMyStudent });
}

export function useMyHomeworkList() {
  return useQuery({ queryKey: meKeys.homework, queryFn: fetchMyHomeworkList });
}

export function useMyHomework(id: string | undefined) {
  return useQuery({
    queryKey: meKeys.homeworkDetail(id ?? ""),
    queryFn: () => fetchMyHomework(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useMyFeedbackList() {
  return useQuery({ queryKey: meKeys.feedback, queryFn: fetchMyFeedbackList });
}

export function useMyFeedback(id: string | undefined) {
  return useQuery({
    queryKey: meKeys.feedbackDetail(id ?? ""),
    queryFn: () => fetchMyFeedback(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useMyPlans() {
  return useQuery({ queryKey: meKeys.plans, queryFn: fetchMyPlans });
}

export function useMySessions() {
  return useQuery({ queryKey: meKeys.sessions, queryFn: fetchMySessions });
}

/** Saves the answers so far. No `status`, so the homework stays assigned. */
export function useSaveAnswers() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, submission }: { id: string; submission: string }) =>
      directus.request(updateItem("homework", id, { submission }, { fields: ["id", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: meKeys.all });
    },
  });
}

// Handing in is one write: the answers, the moment, and the status together. Directus
// allows it only while the row is still assigned, so a second hand-in is refused by the
// permission rather than by this hook.
export function useHandInHomework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, submission }: { id: string; submission: string }) =>
      directus.request(
        updateItem(
          "homework",
          id,
          { submission, submitted_at: new Date().toISOString(), status: "submitted" },
          { fields: ["id", "status", "submitted_at"] }
        )
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: meKeys.all });
    },
  });
}
