// Sessions are the one place the app reads and writes a wall-clock time, so the
// conversions between an ISO timestamp and the tutor's own clock live together here.

import { relativeDay } from "@/lib/format";

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function parse(iso: string | null): Date | null {
  if (!iso) {
    return null;
  }
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? null : at;
}

/** Splits a timestamp into the values `<input type="date">` and `type="time"` want. */
export function toDateTimeInputs(iso: string | null): { date: string; time: string } {
  const at = parse(iso);
  if (!at) {
    return { date: "", time: "" };
  }
  return {
    date: `${String(at.getFullYear())}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`,
    time: `${pad(at.getHours())}:${pad(at.getMinutes())}`,
  };
}

/** The reverse: local date + time as the tutor typed them, back to a timestamp. */
export function fromDateTimeInputs(date: string, time: string): string | null {
  if (!date) {
    return null;
  }
  const at = new Date(`${date}T${time || "00:00"}`);
  return Number.isNaN(at.getTime()) ? null : at.toISOString();
}

/** Local calendar day, for grouping sessions under one heading. */
export function dayKey(iso: string | null): string {
  const at = parse(iso);
  if (!at) {
    return "";
  }
  return `${String(at.getFullYear())}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
}

export function formatDayHeading(iso: string | null): string {
  return relativeDay(iso);
}

export function formatTime(iso: string | null): string {
  const at = parse(iso);
  if (!at) {
    return "No time set";
  }
  return at.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function formatDuration(minutes: number | null): string {
  if (!minutes || minutes <= 0) {
    return "No length set";
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const parts: string[] = [];
  if (hours > 0) {
    parts.push(hours === 1 ? "1 hour" : `${String(hours)} hours`);
  }
  if (rest > 0) {
    parts.push(rest === 1 ? "1 minute" : `${String(rest)} minutes`);
  }
  return parts.join(" ");
}
