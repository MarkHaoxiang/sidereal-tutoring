import { useId, useMemo } from "react";
import type { ReactNode } from "react";

import { cx } from "@/lib/cx";

import { FieldContext } from "./field-context";
import styles from "./Field.module.css";

export interface FieldProps {
  label: string;
  help?: string;
  error?: string | null;
  required?: boolean;
  className?: string;
  children: ReactNode;
}

export function Field({ label, help, error, required = false, className, children }: FieldProps) {
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;

  const control = useMemo(() => {
    const describedBy = cx(help ? helpId : undefined, error ? errorId : undefined);
    return {
      id,
      ...(describedBy ? { "aria-describedby": describedBy } : {}),
      ...(error ? { "aria-invalid": true as const } : {}),
    };
  }, [id, help, helpId, error, errorId]);

  return (
    <div className={cx(styles.field, className)}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      <FieldContext.Provider value={control}>{children}</FieldContext.Provider>
      {help ? (
        <p id={helpId} className={styles.help}>
          {help}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
