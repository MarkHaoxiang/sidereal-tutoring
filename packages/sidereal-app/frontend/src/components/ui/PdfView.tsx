import { Download, ExternalLink } from "lucide-react";

import { cx } from "@/lib/cx";
import { useFileBlob } from "@/lib/files";

import { Spinner } from "./Spinner";
import buttonStyles from "./Button.module.css";
import styles from "./PdfView.module.css";

export interface PdfViewProps {
  fileId: string;
  /** Used until Directus says what the file is called, and if it never does. */
  fallbackName: string;
  className?: string;
}

const buttonClass = cx(buttonStyles.button, buttonStyles.secondary, buttonStyles.sm, styles.link);

/**
 * A Directus PDF, shown in place. The bytes are fetched with the caller's token and held as an
 * object URL, so neither the frame nor the two links ever carry a token in a URL.
 */
export function PdfView({ fileId, fallbackName, className }: PdfViewProps) {
  const { url, name, isLoading, error } = useFileBlob(fileId, fallbackName);

  if (isLoading) {
    return (
      <p className={styles.status}>
        <Spinner /> Loading the PDF…
      </p>
    );
  }

  if (error !== null || url === null) {
    return <p className={styles.error}>{error ?? "This PDF could not be opened."}</p>;
  }

  return (
    <div className={cx(styles.view, className)}>
      <object data={url} type="application/pdf" className={styles.frame} aria-label={`${name}, as a PDF`}>
        <p className={styles.fallback}>
          This browser will not show the PDF here. Open or download it instead.
        </p>
      </object>
      <div className={styles.actions}>
        <a className={buttonClass} href={url} target="_blank" rel="noreferrer">
          <ExternalLink size={14} aria-hidden="true" />
          Open PDF
        </a>
        <a className={buttonClass} href={url} download={name}>
          <Download size={14} aria-hidden="true" />
          Download
        </a>
      </div>
    </div>
  );
}
