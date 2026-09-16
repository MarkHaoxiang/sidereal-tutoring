function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/**
 * Who added a piece of material. A tutor reads no other tutor's login, so `user_created`
 * arrives as a bare id or null for a colleague's row and only the anonymous name is left.
 */
export function addedByName(user: unknown, selfId: string | null): string {
  const row = asRecord(user);
  const id = text(user) ?? text(row?.["id"]);
  if (id && id === selfId) {
    return "You";
  }
  const name = [text(row?.["first_name"]), text(row?.["last_name"])].filter(Boolean).join(" ");
  return name || "A colleague";
}
