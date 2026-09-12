import { cx } from "@/lib/cx";

import styles from "./topics.module.css";

export interface TopicChipsProps {
  topics: { id: string; name: string }[];
  /** Shown instead of the chips when nothing is tagged; omit to render nothing. */
  empty?: string;
  className?: string;
}

export function TopicChips({ topics, empty, className }: TopicChipsProps) {
  if (topics.length === 0) {
    return empty ? <span className={cx(styles.empty, className)}>{empty}</span> : null;
  }
  return (
    <span className={cx(styles.chips, className)}>
      {topics.map((topic) => (
        <span key={topic.id} className={styles.chip}>
          {topic.name}
        </span>
      ))}
    </span>
  );
}
