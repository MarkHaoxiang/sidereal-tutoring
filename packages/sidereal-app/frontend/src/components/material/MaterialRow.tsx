import { Link } from "react-router-dom";
import { toast } from "sonner";

import { TopicChips } from "@/components/topics/TopicChips";
import { Button, StatusChip } from "@/components/ui";
import { apiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useRetryDocument } from "@/lib/queries";
import type { DocumentListItem } from "@/lib/queries";

import styles from "./material.module.css";

export interface MaterialRowProps {
  document: DocumentListItem;
  to: string;
  /** Library rows carry what the material covers and who put it there. */
  topics?: { id: string; name: string }[];
  addedBy?: string;
}

export function MaterialRow({ document, to, topics, addedBy }: MaterialRowProps) {
  const retry = useRetryDocument();
  const pageCount = (document.pages ?? []).length;

  const tryAgain = async () => {
    try {
      await retry.mutateAsync(document.id);
      toast.success("Reading again");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <li className={styles.row}>
      <Link to={to} className={styles.link}>
        <span className={styles.title}>{document.title ?? "Untitled material"}</span>
        <StatusChip status={document.kind} />
        <StatusChip status={document.status} />
        <span className={styles.meta}>
          {pageCount > 0 ? <span>{pageCount === 1 ? "1 page" : `${String(pageCount)} pages`}</span> : null}
          {topics && topics.length > 0 ? <TopicChips topics={topics} /> : null}
          <span>{formatDateTime(document.date_created)}</span>
          {addedBy ? <span>by {addedBy}</span> : null}
        </span>
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
