import { cx } from "@/lib/cx";

import { Mark } from "./Mark";
import styles from "./Wordmark.module.css";

export interface WordmarkProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Wordmark({ size = "md", className }: WordmarkProps) {
  return (
    <span className={cx(styles.wordmark, styles[size], className)}>
      <Mark size={size === "lg" ? 30 : size === "md" ? 22 : 20} className={styles.mark} />
      <span className={styles.words}>
        <span className={styles.name}>Sidereal</span>
        <span className={styles.suffix}>Tutoring</span>
      </span>
    </span>
  );
}
