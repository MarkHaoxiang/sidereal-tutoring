import { taggedTopics } from "@/components/topics/tree";
import type { LibraryDocument } from "@/lib/queries";

export interface LibraryFilter {
  search: string;
  topic: string | null;
}

export function libraryTopicsOf(document: LibraryDocument): { id: string; name: string }[] {
  return taggedTopics(document.topics).map((topic) => ({ id: topic.id, name: topic.name }));
}

/** Every topic tagged on the material shown, by name: offering the rest would filter to nothing. */
export function libraryTopics(documents: LibraryDocument[]): { id: string; name: string }[] {
  const seen = new Map<string, string>();
  for (const document of documents) {
    for (const topic of libraryTopicsOf(document)) {
      seen.set(topic.id, topic.name);
    }
  }
  return [...seen]
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function matchesLibraryFilter(document: LibraryDocument, filter: LibraryFilter): boolean {
  const term = filter.search.trim().toLowerCase();
  if (term && !(document.title ?? "").toLowerCase().includes(term)) {
    return false;
  }
  return filter.topic === null || libraryTopicsOf(document).some((topic) => topic.id === filter.topic);
}
