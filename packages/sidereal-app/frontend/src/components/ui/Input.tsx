import type { InputHTMLAttributes } from "react";

import { cx } from "@/lib/cx";

import { useFieldControl } from "./field-context";
import styles from "./control.module.css";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, type = "text", ...rest }: InputProps) {
  const field = useFieldControl();
  return <input type={type} className={cx(styles.control, className)} {...field} {...rest} />;
}
