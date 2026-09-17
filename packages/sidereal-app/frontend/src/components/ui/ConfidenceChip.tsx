import { cx } from "@/lib/cx";
import type { TranscriptionConfidence } from "@/lib/schema";

import styles from "./StatusChip.module.css";

const TOKENS: Record<TranscriptionConfidence, { label: string; tone: "success" | "warning" | "danger" }> = {
  high: { label: "Clear", tone: "success" },
  medium: { label: "Some guesses", tone: "warning" },
  low: { label: "Hard to read", tone: "danger" },
};

export interface ConfidenceChipProps {
  confidence: TranscriptionConfidence;
  className?: string;
}

/** How well the handwriting was read, in the tutor's words rather than the model's. */
export function ConfidenceChip({ confidence, className }: ConfidenceChipProps) {
  const { label, tone } = TOKENS[confidence];
  return <span className={cx(styles.chip, styles[tone], className)}>{label}</span>;
}
