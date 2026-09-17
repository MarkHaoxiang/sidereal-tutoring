import { Download, ExternalLink } from "lucide-react";

import { cx } from "@/lib/cx";
import { useFileBlob } from "@/lib/files";
import { useMediaQuery } from "@/lib/media";

import { Spinner } from "./Spinner";
import buttonStyles from "./Button.module.css";
import styles from "./PdfView.module.css";

export interface PdfViewProps {
  fileId: string;
  /** Used until Directus says what the file is called, and if it never does. */
  fallbackName: string;
  className?: string;
}

// An A4 page in a phone-width box is a grey blur, so below this the embed is replaced by the
// two things that do work there: opening it full screen, and saving it.
const ROOM_FOR_A_PAGE = "(min-width: 40rem)";

const buttonClass = cx(buttonStyles.button, buttonStyles.secondary, buttonStyles.sm, styles.link);
const openClass = cx(buttonStyles.button, buttonStyles.primary, styles.link, styles.open);
const downloadClass = cx(buttonStyles.button, buttonStyles.secondary, styles.link, styles.open);

/**
 * A Directus PDF, shown in place. The bytes are fetched with the caller's token and held as an
 * object URL, so neither the frame nor the two links ever carry a token in a URL.
 */
export function PdfView({ fileId, fallbackName, className }: PdfViewProps) {
  const { url, name, isLoading, error } = useFileBlob(fileId, fallbackName);
  const roomForAPage = useMediaQuery(ROOM_FOR_A_PAGE);

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

  if (!roomForAPage) {
    return (
      <div className={cx(styles.view, styles.phone, className)}>
        <a className={openClass} href={url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} aria-hidden="true" />
          Open PDF
        </a>
        <a className={downloadClass} href={url} download={name}>
          <Download size={16} aria-hidden="true" />
          Download
        </a>
      </div>
    );
  }

  return (
    <div className={cx(styles.view, className)}>
      <object data={url} type="application/pdf" className={styles.frame} aria-label={`${name}, as a PDF`}>
        <p className={styles.fallback}>This browser will not show the PDF here.</p>
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
