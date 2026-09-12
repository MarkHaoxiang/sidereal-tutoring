import { Paperclip } from "lucide-react";

import { cx } from "@/lib/cx";
import { useFileBlob } from "@/lib/files";

import { Spinner } from "./Spinner";
import styles from "./FileLink.module.css";

export interface FileLinkProps {
  fileId: string;
  /** Used until Directus says what the file is called, and if it never does. */
  fallbackName: string;
  className?: string;
}

/** A Directus file, opened in a new tab from bytes this caller's token was allowed to fetch. */
export function FileLink({ fileId, fallbackName, className }: FileLinkProps) {
  const { url, name, isLoading, error } = useFileBlob(fileId, fallbackName);

  if (isLoading) {
    return (
      <span className={cx(styles.status, className)}>
        <Spinner size="sm" /> {name}
      </span>
    );
  }

  if (error !== null || url === null) {
    return <span className={cx(styles.error, className)}>{error ?? "This file could not be opened."}</span>;
  }

  return (
    <a className={cx(styles.link, className)} href={url} target="_blank" rel="noreferrer">
      <Paperclip size={14} aria-hidden="true" />
      {name}
    </a>
  );
}
