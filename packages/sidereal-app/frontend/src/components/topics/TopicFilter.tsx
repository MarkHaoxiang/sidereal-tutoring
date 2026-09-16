import { cx } from "@/lib/cx";

import styles from "./topics.module.css";

export interface TopicFilterProps {
  /** Only the topics actually tagged on what is listed; the rest would filter to nothing. */
  topics: { id: string; name: string }[];
  value: string | null;
  onChange: (next: string | null) => void;
  label?: string;
  className?: string;
}

export function TopicFilter({ topics, value, onChange, label = "Filter by topic", className }: TopicFilterProps) {
  if (topics.length === 0) {
    return null;
  }
  return (
    <div className={cx(styles.filter, className)} role="group" aria-label={label}>
      <button
        type="button"
        className={styles.filterChip}
        aria-pressed={value === null}
        onClick={() => {
          onChange(null);
        }}
      >
        All topics
      </button>
      {topics.map((topic) => (
        <button
          key={topic.id}
          type="button"
          className={styles.filterChip}
          aria-pressed={value === topic.id}
          onClick={() => {
            onChange(value === topic.id ? null : topic.id);
          }}
        >
          {topic.name}
        </button>
      ))}
    </div>
  );
}
