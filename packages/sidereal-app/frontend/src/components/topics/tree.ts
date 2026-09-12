import { relationId } from "@/lib/queries";
import type { TopicRow } from "@/lib/queries";

export interface TopicNode {
  topic: TopicRow;
  depth: number;
  children: TopicNode[];
}

export const BREADCRUMB_SEPARATOR = " › ";

export function parentId(topic: TopicRow): string | null {
  return relationId(topic.parent);
}

function byOrder(a: TopicRow, b: TopicRow): number {
  const left = a.sort ?? Number.MAX_SAFE_INTEGER;
  const right = b.sort ?? Number.MAX_SAFE_INTEGER;
  return left === right ? a.name.localeCompare(b.name) : left - right;
}

/**
 * The tree, rooted at every topic whose parent is absent — a topic pointing at one that is
 * gone sits at the root rather than disappearing.
 */
export function buildTopicTree(topics: TopicRow[]): TopicNode[] {
  const known = new Set(topics.map((topic) => topic.id));
  const children = new Map<string, TopicRow[]>();
  const roots: TopicRow[] = [];

  for (const topic of topics) {
    const parent = parentId(topic);
    if (parent === null || !known.has(parent) || parent === topic.id) {
      roots.push(topic);
      continue;
    }
    children.set(parent, [...(children.get(parent) ?? []), topic]);
  }

  const build = (row: TopicRow, depth: number, seen: Set<string>): TopicNode => {
    const next = new Set(seen).add(row.id);
    return {
      topic: row,
      depth,
      children: (children.get(row.id) ?? [])
        .filter((child) => !next.has(child.id))
        .sort(byOrder)
        .map((child) => build(child, depth + 1, next)),
    };
  };

  return roots.sort(byOrder).map((root) => build(root, 0, new Set()));
}

/** Every topic's ancestors and itself, by id — "Algebra", "Quadratics". */
export function topicPaths(topics: TopicRow[]): Map<string, string[]> {
  const byId = new Map(topics.map((topic) => [topic.id, topic]));
  const paths = new Map<string, string[]>();

  const walk = (topic: TopicRow, seen: Set<string>): string[] => {
    const cached = paths.get(topic.id);
    if (cached) {
      return cached;
    }
    const parent = parentId(topic);
    const above = parent === null || seen.has(parent) ? undefined : byId.get(parent);
    const path = above ? [...walk(above, new Set(seen).add(topic.id)), topic.name] : [topic.name];
    paths.set(topic.id, path);
    return path;
  };

  for (const topic of topics) {
    walk(topic, new Set());
  }
  return paths;
}

export function breadcrumb(path: string[] | undefined): string {
  return (path ?? []).join(BREADCRUMB_SEPARATOR);
}

interface TaggedTopic {
  id: string;
  name: string;
  sort: number;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

/**
 * The topics behind a `<collection>_topics` alias, in the order they were tagged. The SDK types
 * a nested alias loosely, so the rows are read defensively.
 */
export function taggedTopics(value: unknown): TaggedTopic[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const rows = value.flatMap((entry) => {
    const link = asRecord(entry);
    const topic = asRecord(link?.["topic"]);
    const id = topic?.["id"];
    const name = topic?.["name"];
    if (typeof id !== "string" || typeof name !== "string") {
      return [];
    }
    const sort = link?.["sort"];
    return [{ id, name, sort: typeof sort === "number" ? sort : Number.MAX_SAFE_INTEGER }];
  });
  return rows.sort((a, b) => a.sort - b.sort);
}

export function taggedTopicIds(value: unknown): string[] {
  return taggedTopics(value).map((topic) => topic.id);
}
