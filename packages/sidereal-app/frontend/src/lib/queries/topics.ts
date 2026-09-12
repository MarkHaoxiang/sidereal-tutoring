import { createItem, deleteItem, deleteItems, readItems, updateItem } from "@directus/sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { directus } from "@/lib/directus";

import { documentKeys } from "./documents";
import { homeworkKeys } from "./homework";

export const topicKeys = {
  all: ["topics"] as const,
  list: ["topics", "list"] as const,
  usage: (id: string) => ["topics", "usage", id] as const,
};

function fetchTopics() {
  return directus.request(
    readItems("topics", {
      fields: ["id", "name", "parent", "description", "sort"],
      sort: ["sort", "name"],
      limit: -1,
    })
  );
}

export type TopicRow = Awaited<ReturnType<typeof fetchTopics>>[number];

export interface TopicInput {
  name: string;
  parent?: string | null;
  description?: string | null;
}

export interface TopicUsage {
  documents: number;
  questions: number;
  homework: number;
}

/** Whole tree, always: it is small, and every consumer needs the ancestors of what it shows. */
export function useTopics() {
  return useQuery({ queryKey: topicKeys.list, queryFn: fetchTopics });
}

async function fetchUsage(topicId: string): Promise<TopicUsage> {
  const filter = { topic: { _eq: topicId } };
  const [documents, questions, homework] = await Promise.all([
    directus.request(readItems("document_topics", { fields: ["id"], filter, limit: -1 })),
    directus.request(readItems("question_topics", { fields: ["id"], filter, limit: -1 })),
    directus.request(readItems("homework_topics", { fields: ["id"], filter, limit: -1 })),
  ]);
  return { documents: documents.length, questions: questions.length, homework: homework.length };
}

export function useTopicUsage(topicId: string | null) {
  return useQuery({
    queryKey: topicKeys.usage(topicId ?? ""),
    queryFn: () => fetchUsage(topicId ?? ""),
    enabled: Boolean(topicId),
  });
}

export function useCreateTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TopicInput) =>
      directus.request(createItem("topics", input, { fields: ["id", "name"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: topicKeys.all });
    },
  });
}

export function useUpdateTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<TopicInput> }) =>
      directus.request(updateItem("topics", id, patch, { fields: ["id", "name"] })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: topicKeys.all });
    },
  });
}

/** Deleting promotes the children (the relation is SET NULL) and drops the tags (they cascade). */
export function useDeleteTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => directus.request(deleteItem("topics", id)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: topicKeys.all });
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
    },
  });
}

/** The id of a relational field, however far the SDK expanded it. */
export function relationId(value: unknown): string | null {
  if (typeof value === "string") {
    return value;
  }
  const row = typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
  const id = row?.["id"];
  return typeof id === "string" ? id : null;
}

interface Link {
  id: string;
  topic: string | null;
}

function diffLinks(existing: Link[], next: string[]) {
  return {
    add: next.filter((topic) => !existing.some((link) => link.topic === topic)),
    remove: existing.filter((link) => link.topic === null || !next.includes(link.topic)).map((link) => link.id),
  };
}

async function setDocumentTopics(documentId: string, topics: string[]) {
  const existing = await directus.request(
    readItems("document_topics", {
      fields: ["id", "topic"],
      filter: { document: { _eq: documentId } },
      limit: -1,
    })
  );
  const { add, remove } = diffLinks(
    existing.map((link) => ({ id: link.id, topic: relationId(link.topic) })),
    topics
  );
  if (remove.length > 0) {
    await directus.request(deleteItems("document_topics", remove));
  }
  await Promise.all(
    add.map((topic) =>
      directus.request(
        createItem("document_topics", { document: documentId, topic, sort: topics.indexOf(topic) + 1 })
      )
    )
  );
}

async function setHomeworkTopics(homeworkId: string, topics: string[]) {
  const existing = await directus.request(
    readItems("homework_topics", {
      fields: ["id", "topic"],
      filter: { homework: { _eq: homeworkId } },
      limit: -1,
    })
  );
  const { add, remove } = diffLinks(
    existing.map((link) => ({ id: link.id, topic: relationId(link.topic) })),
    topics
  );
  if (remove.length > 0) {
    await directus.request(deleteItems("homework_topics", remove));
  }
  await Promise.all(
    add.map((topic) =>
      directus.request(
        createItem("homework_topics", { homework: homeworkId, topic, sort: topics.indexOf(topic) + 1 })
      )
    )
  );
}

/** Replaces the material's tags with exactly this selection. */
export function useTagDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, topics }: { id: string; topics: string[] }) => setDocumentTopics(id, topics),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all });
      void queryClient.invalidateQueries({ queryKey: topicKeys.all });
    },
  });
}

/** Replaces the homework's tags with exactly this selection. */
export function useTagHomework() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, topics }: { id: string; topics: string[] }) => setHomeworkTopics(id, topics),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: homeworkKeys.all });
      void queryClient.invalidateQueries({ queryKey: topicKeys.all });
    },
  });
}
