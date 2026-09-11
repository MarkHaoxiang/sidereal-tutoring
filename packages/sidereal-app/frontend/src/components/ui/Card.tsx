import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "@/lib/cx";

import styles from "./Card.module.css";

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  /** Renders a header row above the body; `actions` sits at its right edge. */
  title?: ReactNode;
  actions?: ReactNode;
  padded?: boolean;
}

export function Card({ title, actions, padded = true, className, children, ...rest }: CardProps) {
  return (
    <section className={cx(styles.card, className)} {...rest}>
      {title || actions ? (
        <header className={styles.header}>
          {typeof title === "string" ? <h2 className={styles.title}>{title}</h2> : title}
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </header>
      ) : null}
      <div className={cx(padded && styles.body)}>{children}</div>
    </section>
  );
}
