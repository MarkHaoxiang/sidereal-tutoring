import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Mark } from "@/components/Mark";
import { cx } from "@/lib/cx";

import styles from "./PageHeader.module.css";

export interface PageHeaderProps {
  /** The small line above the title saying where you are. */
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  /** Buttons for this page, at the right edge of the title row. */
  actions?: ReactNode;
  /** The way back up, shown above everything else. */
  back?: { to: string; label: string };
  /** Chips and dates that describe what the title names. */
  meta?: ReactNode;
  className?: string;
}

export function PageHeader({ eyebrow, title, subtitle, actions, back, meta, className }: PageHeaderProps) {
  return (
    <header className={cx(styles.header, className)}>
      {back ? (
        <Link to={back.to} className={styles.back}>
          <ArrowLeft size={14} aria-hidden="true" />
          {back.label}
        </Link>
      ) : null}

      <div className={styles.row}>
        <div className={styles.titleBlock}>
          {eyebrow ? (
            <p className={styles.eyebrow}>
              <Mark size={11} />
              {eyebrow}
            </p>
          ) : null}
          <h1 className={styles.title}>{title}</h1>
          {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
        </div>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>

      {meta ? <div className={styles.meta}>{meta}</div> : null}
    </header>
  );
}
