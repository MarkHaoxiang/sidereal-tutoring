import styles from "@/components/papers/papers.module.css";
import { Button, PdfView } from "@/components/ui";
import { fileIdOf } from "@/lib/files";

import { needsMarkScheme, usePaperTab } from "./context";

export function PrintableTab() {
  const { paper, rendering, rerender, makeWorksheet, extractScheme } = usePaperTab();
  const renderedPdf = fileIdOf(paper.rendered_pdf);
  const schemePdf = fileIdOf(paper.mark_scheme_pdf);
  const needsScheme = needsMarkScheme(paper);

  return (
    <div className={styles.stack}>
      <div className={styles.tabActions}>
        <Button onClick={makeWorksheet}>Make worksheet</Button>
        <Button variant={needsScheme ? "primary" : "secondary"} onClick={extractScheme}>
          {needsScheme ? "Extract mark scheme" : "Re-extract mark scheme"}
        </Button>
        <Button loading={rendering} onClick={rerender}>
          Re-render
        </Button>
      </div>

      {renderedPdf === null && schemePdf === null ? (
        <p className={styles.status}>No PDFs yet — choose Re-render.</p>
      ) : (
        <div className={styles.pdfs}>
          {renderedPdf ? (
            <div className={styles.pdf}>
              <p className={styles.pdfLabel}>Paper</p>
              <PdfView fileId={renderedPdf} fallbackName={`${paper.title}.pdf`} />
            </div>
          ) : null}
          {schemePdf ? (
            <div className={styles.pdf}>
              <p className={styles.pdfLabel}>Mark scheme</p>
              <PdfView fileId={schemePdf} fallbackName={`${paper.title} mark scheme.pdf`} />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
