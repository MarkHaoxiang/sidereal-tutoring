// One clock for every date the app writes, so a lesson is never "Tomorrow" on one screen
// and a weekday on the next.

/** A calendar date (`2026-09-24`) is local, not UTC midnight; anything else is a timestamp. */
function parse(value: string): Date | null {
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const parsed = day
    ? new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3]))
    : new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function midnight(at: Date): number {
  return new Date(at.getFullYear(), at.getMonth(), at.getDate()).getTime();
}

const DAY_MS = 86_400_000;

export function formatDate(value: string | null): string {
  if (!value) {
    return "No date set";
  }
  const parsed = parse(value);
  if (!parsed) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(value: string | null): string {
  if (!value) {
    return "No date set";
  }
  const parsed = parse(value);
  if (!parsed) {
    return value;
  }
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * The day, as a person would say it: Today, Tomorrow, Yesterday, the weekday for the rest of
 * this week, and the date beyond that. Every relative date in the app comes through here.
 */
export function relativeDay(value: string | null, now: Date = new Date()): string {
  if (!value) {
    return "No date set";
  }
  const parsed = parse(value);
  if (!parsed) {
    return value;
  }
  const days = Math.round((midnight(parsed) - midnight(now)) / DAY_MS);
  if (days === 0) {
    return "Today";
  }
  if (days === 1) {
    return "Tomorrow";
  }
  if (days === -1) {
    return "Yesterday";
  }
  if (days > 1 && days <= 6) {
    return parsed.toLocaleDateString(undefined, { weekday: "long" });
  }
  return formatDate(value);
}
