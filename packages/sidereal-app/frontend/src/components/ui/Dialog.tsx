import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import type { MouseEvent, ReactNode } from "react";

import styles from "./Dialog.module.css";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Buttons for the bottom row; the caller owns their order and variants. */
  footer?: ReactNode;
  /** While true, Escape and backdrop clicks are ignored — a submission is in flight. */
  busy?: boolean;
}

export function Dialog({ open, onClose, title, children, footer, busy = false }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
      // The opener may have re-rendered while the dialog was up, so check it is still
      // in the document before handing focus back to it.
      if (openerRef.current?.isConnected) {
        openerRef.current.focus();
      }
      openerRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    // Escape fires `cancel`; let `open` drive the element instead of letting the
    // browser close it behind React's back.
    const handleCancel = (event: Event) => {
      event.preventDefault();
      if (!busy) {
        onClose();
      }
    };
    dialog.addEventListener("cancel", handleCancel);
    return () => {
      dialog.removeEventListener("cancel", handleCancel);
    };
  }, [busy, onClose]);

  const handleClick = (event: MouseEvent<HTMLDialogElement>) => {
    // The <dialog> box is the backdrop; everything visible sits in .panel inside it.
    if (event.target === dialogRef.current && !busy) {
      onClose();
    }
  };

  return (
    <dialog ref={dialogRef} className={styles.dialog} aria-labelledby={titleId} onClick={handleClick}>
      <div className={styles.panel}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>
        <div className={styles.body}>{children}</div>
        {footer ? <footer className={styles.footer}>{footer}</footer> : null}
      </div>
    </dialog>
  );
}
