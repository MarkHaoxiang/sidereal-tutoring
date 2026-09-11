import type { SelectHTMLAttributes } from "react";

import { cx } from "@/lib/cx";

import { useFieldControl } from "./field-context";
import styles from "./control.module.css";

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export function Select({ className, children, ...rest }: SelectProps) {
  const field = useFieldControl();
  return (
    <select className={cx(styles.control, styles.select, className)} {...field} {...rest}>
      {children}
    </select>
  );
}
