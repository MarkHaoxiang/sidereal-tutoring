import styles from "@/components/papers/papers.module.css";
import { Button, PdfView } from "@/components/ui";
import { fileIdOf } from "@/lib/files";

import { usePaperTab } from "./context";

export function PrintableTab() {
  const { paper, rendering, rerender, makeWorksheet } = usePaperTab();
  const renderedPdf = fileIdOf(paper.rendered_pdf);
  const schemePdf = fileIdOf(paper.mark_scheme_pdf);

  return (
    <div className={styles.stack}>
      <div className={styles.tabActions}>
        <Button onClick={makeWorksheet}>Make a worksheet</Button>
        <Button loading={rendering} onClick={rerender}>
          Re-render
        </Button>
      </div>

      {renderedPdf === null && schemePdf === null ? (
        <p className={styles.status}>
          There are no PDFs yet. Re-render to make them from the structure.
        </p>
      ) : (
        <div className={styles.pdfs}>
          {renderedPdf ? (
            <div className={styles.pdf}>
              <p className={styles.pdfLabel}>The paper</p>
              <PdfView fileId={renderedPdf} fallbackName={`${paper.title}.pdf`} />
            </div>
          ) : null}
          {schemePdf ? (
            <div className={styles.pdf}>
              <p className={styles.pdfLabel}>The mark scheme</p>
              <PdfView fileId={schemePdf} fallbackName={`${paper.title} mark scheme.pdf`} />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
