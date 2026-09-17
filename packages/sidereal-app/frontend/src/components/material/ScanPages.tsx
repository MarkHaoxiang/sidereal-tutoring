import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Spinner } from "@/components/ui";
import { useFileBlob } from "@/lib/files";

import styles from "./scan.module.css";

function PageImage({ fileId, page, className }: { fileId: string; page: number; className?: string }) {
  const { url, isLoading, error } = useFileBlob(fileId, `Page ${String(page)}`);

  if (isLoading) {
    return (
      <span className={styles.pageWait}>
        <Spinner size="sm" />
      </span>
    );
  }
  if (error !== null || url === null) {
    return <span className={styles.pageWait}>Page {page}</span>;
  }
  return <img src={url} alt={`Page ${String(page)}`} className={className} />;
}

function Lightbox({
  fileIds,
  index,
  onIndex,
  onClose,
}: {
  fileIds: string[];
  index: number;
  onIndex: (next: number) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
    };
  }, []);

  const step = (delta: -1 | 1) => {
    onIndex((index + delta + fileIds.length) % fileIds.length);
  };

  return (
    <dialog
      ref={ref}
      className={styles.lightbox}
      aria-label={`Page ${String(index + 1)} of ${String(fileIds.length)}`}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) {
          onClose();
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") {
          step(-1);
        }
        if (event.key === "ArrowRight") {
          step(1);
        }
      }}
    >
      <div className={styles.lightboxPanel}>
        <PageImage fileId={fileIds[index] ?? ""} page={index + 1} className={styles.lightboxImage} />
      </div>
      <div className={styles.lightboxBar}>
        {fileIds.length > 1 ? (
          <button
            type="button"
            className={styles.lightboxButton}
            aria-label="Previous page"
            onClick={() => {
              step(-1);
            }}
          >
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
        ) : null}
        <span className={styles.lightboxCount}>
          {index + 1} / {fileIds.length}
        </span>
        {fileIds.length > 1 ? (
          <button
            type="button"
            className={styles.lightboxButton}
            aria-label="Next page"
            onClick={() => {
              step(1);
            }}
          >
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        ) : null}
        <button type="button" className={styles.lightboxButton} aria-label="Close" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>
    </dialog>
  );
}

/** The photos a scan was read from, in order, each opening full size. */
export function ScanPages({ fileIds }: { fileIds: string[] }) {
  const [open, setOpen] = useState<number | null>(null);

  if (fileIds.length === 0) {
    return null;
  }

  return (
    <div>
      <ul className={styles.pages}>
        {fileIds.map((fileId, index) => (
          <li key={fileId}>
            <button
              type="button"
              className={styles.page}
              aria-label={`Page ${String(index + 1)}`}
              onClick={() => {
                setOpen(index);
              }}
            >
              <PageImage fileId={fileId} page={index + 1} className={styles.pageImage} />
              <span className={styles.pageNumber}>{index + 1}</span>
            </button>
          </li>
        ))}
      </ul>
      {open !== null ? (
        <Lightbox
          fileIds={fileIds}
          index={open}
          onIndex={setOpen}
          onClose={() => {
            setOpen(null);
          }}
        />
      ) : null}
    </div>
  );
}
