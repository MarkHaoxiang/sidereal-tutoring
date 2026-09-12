import type { ReactNode } from "react";

import { Constellation } from "@/components/Mark";

import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  message: string;
  /** The obvious next step — a Button, usually. */
  action?: ReactNode;
}

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <Constellation size={132} className={styles.mark} />
      <p className={styles.message}>{message}</p>
      {action}
    </div>
  );
}
