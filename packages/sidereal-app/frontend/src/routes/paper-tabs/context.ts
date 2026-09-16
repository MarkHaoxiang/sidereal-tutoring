import { useOutletContext } from "react-router-dom";

import type { PaperDraft } from "@/components/papers/draft";
import type { PaperDetail } from "@/lib/queries";

export interface PaperTabContext {
  paper: PaperDetail;
  /** The unsaved paper. Save writes the whole structure; a tab only ever edits this. */
  draft: PaperDraft;
  edit: (patch: Partial<PaperDraft>) => void;
  rendering: boolean;
  rerender: () => void;
  /** Opens the worksheet dialog the page holds. */
  makeWorksheet: () => void;
}

/** The paper from `/library/papers/:paperId`, handed down by PaperDetailPage. */
export function usePaperTab(): PaperTabContext {
  return useOutletContext<PaperTabContext>();
}
