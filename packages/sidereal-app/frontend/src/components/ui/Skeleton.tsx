import { cx } from "@/lib/cx";

import styles from "./Skeleton.module.css";

export interface SkeletonRowsProps {
  /** How many placeholder rows to draw; match the list it stands in for. */
  count?: number;
  /** Card-shaped rows for lists of cards; `line` for rows inside a card. */
  variant?: "card" | "line";
  /** What the wait is for, announced once rather than per row. */
  label: string;
  className?: string;
}

/**
 * The placeholder a list shows while it loads. It is the shape of the content, not a
 * spinner, so the page does not jump when the rows arrive.
 */
export function SkeletonRows({ count = 3, variant = "card", label, className }: SkeletonRowsProps) {
  return (
    <div className={cx(styles.rows, className)} role="status" aria-label={label} aria-busy="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className={cx(styles.row, styles[variant])}>
          <span className={cx(styles.bar, styles.title)} />
          <span className={cx(styles.bar, styles.meta)} />
        </div>
      ))}
    </div>
  );
}
