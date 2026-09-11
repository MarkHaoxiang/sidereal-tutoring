import { cx } from "@/lib/cx";

import { STATUS_TOKENS } from "./status-tokens";
import type { StatusToken } from "./status-tokens";
import styles from "./StatusChip.module.css";

export interface StatusChipProps {
  status: StatusToken;
  className?: string;
}

export function StatusChip({ status, className }: StatusChipProps) {
  const { label, tone } = STATUS_TOKENS[status];
  return <span className={cx(styles.chip, styles[tone], className)}>{label}</span>;
}
