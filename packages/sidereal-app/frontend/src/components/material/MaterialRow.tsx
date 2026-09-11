import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Button, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useRetryDocument } from "@/lib/queries";
import type { DocumentListItem } from "@/lib/queries";

import styles from "./material.module.css";

export function MaterialRow({ document, to }: { document: DocumentListItem; to: string }) {
  const retry = useRetryDocument();

  const tryAgain = async () => {
    try {
      await retry.mutateAsync(document.id);
      toast.success("Reading this material again");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <li className={styles.row}>
      <Link to={to} className={styles.link}>
        <span className={styles.top}>
          <span className={styles.title}>{document.title ?? "Untitled material"}</span>
          <StatusChip status={document.kind} />
          <StatusChip status={document.status} />
        </span>
        <span className={styles.meta}>Added {formatDateTime(document.date_created)}</span>
      </Link>
      {document.status === "failed" ? (
        <div className={styles.failure}>
          <p className={styles.error}>{document.error ?? "This material could not be read."}</p>
          <Button
            loading={retry.isPending}
            onClick={() => {
              void tryAgain();
            }}
          >
            Retry
          </Button>
        </div>
      ) : null}
    </li>
  );
}
