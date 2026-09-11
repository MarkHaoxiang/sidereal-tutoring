import type { TextareaHTMLAttributes } from "react";

import { cx } from "@/lib/cx";

import { useFieldControl } from "./field-context";
import styles from "./control.module.css";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className, rows = 4, ...rest }: TextareaProps) {
  const field = useFieldControl();
  return <textarea rows={rows} className={cx(styles.control, styles.textarea, className)} {...field} {...rest} />;
}
