import { Link } from "react-router-dom";

import { StatusChip } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { PaperListItem } from "@/lib/queries";

import styles from "./papers.module.css";

export interface PaperRowProps {
  paper: PaperListItem;
  addedBy: string;
}

export function PaperRow({ paper, addedBy }: PaperRowProps) {
  const count = paper.structure?.questions?.length ?? 0;
  const origin = [paper.board, paper.year === null ? null : String(paper.year)].filter(Boolean).join(" · ");

  return (
    <li className={styles.row}>
      <Link to={`/library/papers/${paper.id}`} className={styles.rowLink}>
        <span className={styles.rowTop}>
          <span className={styles.rowTitle}>{paper.title}</span>
          <StatusChip status={paper.status} />
        </span>
        <span className={styles.rowMeta}>
          {origin ? <span>{origin}</span> : null}
          <span>{count === 1 ? "1 question" : `${String(count)} questions`}</span>
          {paper.total_marks === null ? null : <span>{String(paper.total_marks)} marks</span>}
          <span>Added {formatDateTime(paper.date_created)}</span>
          <span>by {addedBy}</span>
        </span>
      </Link>
    </li>
  );
}
