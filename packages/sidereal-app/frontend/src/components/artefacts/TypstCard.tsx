import { toast } from "sonner";

import { Button, PdfView } from "@/components/ui";
import { apiError } from "@/lib/api";
import { useCompileHomework } from "@/lib/queries";

import styles from "./artefacts.module.css";

export interface TypstCardProps {
  homeworkId: string;
  pdfId: string | null;
  pdfName: string;
  compileError: string | null;
}

/** The printable side of a Typst homework: the PDF if there is one, the compiler's report if not. */
export function TypstCard({ homeworkId, pdfId, pdfName, compileError }: TypstCardProps) {
  const compile = useCompileHomework();

  const run = async () => {
    try {
      await compile.mutateAsync(homeworkId);
      toast.success("Compiled");
    } catch (error) {
      toast.error(apiError(error));
    }
  };

  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Typeset</h2>
        {compileError !== null || pdfId === null ? (
          <Button
            loading={compile.isPending}
            onClick={() => {
              void run();
            }}
          >
            {compileError === null ? "Compile" : "Try again"}
          </Button>
        ) : null}
      </div>

      {compileError !== null ? (
        <div className={styles.problem}>
          <p className={styles.problemText}>{compileError}</p>
          <p className={styles.problemNote}>The PDF was not updated.</p>
        </div>
      ) : null}

      {pdfId ? (
        <PdfView fileId={pdfId} fallbackName={pdfName} />
      ) : (
        <p className={styles.status}>No PDF yet.</p>
      )}
    </section>
  );
}
