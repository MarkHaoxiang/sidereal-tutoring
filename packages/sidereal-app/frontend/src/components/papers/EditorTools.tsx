import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";

import { cx } from "@/lib/cx";

import styles from "./papers.module.css";

export interface EditorToolsProps {
  /** What one of these is called, for the buttons' labels: "question 2", "part (a)". */
  label: string;
  index: number;
  count: number;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}

export function EditorTools({ label, index, count, onMove, onRemove }: EditorToolsProps) {
  return (
    <div className={styles.cardTools}>
      <button
        type="button"
        className={styles.tool}
        aria-label={`Move ${label} up`}
        disabled={index === 0}
        onClick={() => {
          onMove(-1);
        }}
      >
        <ChevronUp size={15} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={styles.tool}
        aria-label={`Move ${label} down`}
        disabled={index === count - 1}
        onClick={() => {
          onMove(1);
        }}
      >
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={cx(styles.tool, styles.toolDanger)}
        aria-label={`Remove ${label}`}
        onClick={onRemove}
      >
        <Trash2 size={15} aria-hidden="true" />
      </button>
    </div>
  );
}
