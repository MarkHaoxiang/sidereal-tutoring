import { cx } from "@/lib/cx";

import styles from "./Mark.module.css";

// Both shapes draw in `currentColor`, so a caller sets the colour with `color` and
// nothing else. <Mark> is the small cut and must hold at 16px; <Constellation> is the
// large sparse one.

export function Mark({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={cx(styles.mark, className)}
    >
      <path
        d="M17 40 36 22 55 13"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M17 24C17 35.2 20.75 40 29.5 40C20.75 40 17 44.8 17 56C17 44.8 13.25 40 4.5 40C13.25 40 17 35.2 17 24Z" fill="currentColor" />
      <path d="M36 12.5C36 19.15 38.1 22 43 22C38.1 22 36 24.85 36 31.5C36 24.85 33.9 22 29 22C33.9 22 36 19.15 36 12.5Z" fill="currentColor" />
      <circle cx="55" cy="13" r="4.5" fill="currentColor" />
    </svg>
  );
}

/**
 * The same asterism, drawn large and sparse: the decoration on the login panel and
 * behind every empty state. Purely ornamental, so it is hidden from assistive technology.
 */
export function Constellation({ size = 160, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 160 160"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={cx(styles.constellation, className)}
    >
      <g stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" opacity="0.45">
        <path d="M44 100 88 58 136 38" />
        <path d="M88 58 118 104 150 96" />
        <path d="M44 100 66 138" />
        <path d="M24 40 44 100" />
      </g>
      <path d="M44 74C44 92.98 49.4 100 64 100C49.4 100 44 107.02 44 126C44 107.02 38.6 100 24 100C38.6 100 44 92.98 44 74Z" fill="currentColor" />
      <path d="M88 43C88 53.95 90.97 58 99 58C90.97 58 88 62.05 88 73C88 62.05 85.03 58 77 58C85.03 58 88 53.95 88 43Z" fill="currentColor" opacity="0.85" />
      <path d="M118 94C118 101.3 120.03 104 125.5 104C120.03 104 118 106.7 118 114C118 106.7 115.97 104 110.5 104C115.97 104 118 101.3 118 94Z" fill="currentColor" opacity="0.75" />
      <circle cx="136" cy="38" r="7" fill="currentColor" opacity="0.9" />
      <circle cx="24" cy="40" r="4.5" fill="currentColor" opacity="0.75" />
      <circle cx="66" cy="138" r="5" fill="currentColor" opacity="0.7" />
      <circle cx="150" cy="96" r="4" fill="currentColor" opacity="0.7" />
    </svg>
  );
}
