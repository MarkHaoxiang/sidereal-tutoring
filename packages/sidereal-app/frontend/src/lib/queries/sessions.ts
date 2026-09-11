import { createItem, deleteItem, readItem, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { directus } from "@/lib/directus";
import type { SessionStatus } from "@/lib/schema";

export interface SessionListParams {
  studentId?: string;
  status?: SessionStatus;
  /** ISO datetimes bounding `scheduled_at`. */
  from?: string;
  to?: string;
  sort?: "scheduled_at" | "-scheduled_at";
  limit?: number;
}

export const sessionKeys = {
  all: ["sessions"] as const,
  list: (params: SessionListParams) => ["sessions", "list", params] as const,
  detail: (id: string) => ["sessions", "detail", id] as const,
};

function withinWindow(scheduledAt: string | null, params: SessionListParams): boolean {
  if (!params.from && !params.to) {
    return true;
  }
  if (!scheduledAt) {
    return false;
  }
  const at = Date.parse(scheduledAt);
  if (params.from && at < Date.parse(params.from)) {
    return false;
  }
  return !(params.to && at > Date.parse(params.to));
}

// `from`/`to` are applied here rather than in the filter: the SDK types comparison
// operators as `never` unless the schema declares a field as the literal "datetime",
// which would in turn make every write to that field a literal too. One tutor's
// scheduled sessions are a short list, so the window is cheap to apply client-side.
async function fetchSessions(params: SessionListParams) {
  const rows = await directus.request(
    readItems("sessions", {
      fields: [
        "id",
        "scheduled_at",
        "duration_minutes",
        "notes",
        "status",
        "date_created",
        { student: ["id", "name"] },
      ],
      filter: {
        ...(params.studentId ? { student: { _eq: params.studentId } } : {}),
        ...(params.status ? { status: { _eq: params.status } } : {}),
      },
      sort: [params.sort ?? "-scheduled_at"],
      limit: -1,
    })
  );
  const within = rows.filter((row) => withinWindow(row.scheduled_at, params));
  return params.limit === undefined ? within : within.slice(0, params.limit);
}

function fetchSession(id: string) {
  return directus.request(
    readItem("sessions", id, {
      fields: [
        "id",
        "scheduled_at",
        "duration_minutes",
        "notes",
        "status",
        "date_created",
        { student: ["id", "name"] },
      ],
    })
  );
}

export type SessionListItem = Awaited<ReturnType<typeof fetchSessions>>[number];
export type SessionDetail = Awaited<ReturnType<typeof fetchSession>>;

export interface SessionInput {
  student: string;
  scheduled_at?: string | null;
  duration_minutes?: number | null;
  notes?: string | null;
  status?: SessionStatus;
}

export function useSessions(params: SessionListParams = {}) {
  return useQuery({
    queryKey: sessionKeys.list(params),
    queryFn: () => fetchSessions(params),
  });
}

export function useSession(id: string | undefined) {
  return useQuery({
    queryKey: sessionKeys.detail(id ?? ""),
    queryFn: () => fetchSession(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SessionInput) =>
      directus.request(createItem("sessions", input, { fields: ["id", "scheduled_at", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sessionKeys.all });
    },
  });
}

export function useUpdateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<SessionInput> }) =>
      directus.request(updateItem("sessions", id, patch, { fields: ["id", "scheduled_at", "status"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sessionKeys.all });
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => directus.request(deleteItem("sessions", id)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: sessionKeys.all });
    },
  });
}

export interface SessionLinkCounts {
  /** Material filed against the session. */
  material: number;
  /** Homework and feedback generated for the session. */
  artefacts: number;
}

// What points at each of a student's sessions, in one place: a session row says how
// much material and how many artefacts hang off it. Study plans have no session, so
// they cannot be counted here.
async function fetchSessionLinks(studentId: string): Promise<Record<string, SessionLinkCounts>> {
  const [documents, homework, feedback] = await Promise.all([
    directus.request(
      readItems("documents", {
        fields: ["id", "session"],
        filter: { student: { _eq: studentId } },
        limit: -1,
      })
    ),
    directus.request(
      readItems("homework", {
        fields: ["id", "session"],
        filter: { student: { _eq: studentId } },
        limit: -1,
      })
    ),
    directus.request(
      readItems("feedback", {
        fields: ["id", "session"],
        filter: { student: { _eq: studentId } },
        limit: -1,
      })
    ),
  ]);

  const counts: Record<string, SessionLinkCounts> = {};
  const bump = (sessionId: string | null, key: keyof SessionLinkCounts) => {
    if (!sessionId) {
      return;
    }
    const entry = (counts[sessionId] ??= { material: 0, artefacts: 0 });
    entry[key] += 1;
  };
  for (const row of documents) {
    bump(row.session, "material");
  }
  for (const row of [...homework, ...feedback]) {
    bump(row.session, "artefacts");
  }
  return counts;
}

export function useSessionLinks(studentId: string | undefined) {
  return useQuery({
    queryKey: ["sessions", "links", studentId ?? ""] as const,
    queryFn: () => fetchSessionLinks(studentId ?? ""),
    enabled: Boolean(studentId),
  });
}
