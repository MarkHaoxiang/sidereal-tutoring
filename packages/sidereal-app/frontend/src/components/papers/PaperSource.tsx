import { Copy, Download } from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui";
import { useRenderAssets, useRenderTypst } from "@/lib/queries";
import type { CanonicalPaper } from "@/lib/schema";
import { typstProblem } from "@/lib/typeset";

import { FragmentView } from "./FragmentView";
import styles from "./papers.module.css";

export interface PaperSourceProps {
  structure: CanonicalPaper;
  /** What a downloaded copy is called, without its extension. */
  fileName: string;
}

function save(source: string, fileName: string): void {
  const url = URL.createObjectURL(new Blob([source], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${fileName}.typ`;
  link.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 0);
}

/** The Typst the renderer writes from the structure, beside the pages it compiles to. */
export function PaperSource({ structure, fileName }: PaperSourceProps) {
  const asSource = useMemo(
    () => ({ kind: "paper" as const, document: structure, output: "source" as const }),
    [structure]
  );
  const rendered = useRenderTypst(useRenderAssets(asSource));
  const source = rendered.data?.source ?? null;
  const lines = source === null ? [] : source.split("\n");

  const copy = async () => {
    if (source === null) {
      return;
    }
    try {
      await navigator.clipboard.writeText(source);
      toast.success("Copied");
    } catch {
      toast.error("This browser would not let the page copy it.");
    }
  };

  return (
    <>
      <div className={styles.sourceGrid}>
        <div className={styles.sourcePane}>
          <div className={styles.sourceActions}>
            <Button
              size="sm"
              disabled={source === null}
              onClick={() => {
                void copy();
              }}
            >
              <Copy size={14} aria-hidden="true" />
              Copy
            </Button>
            <Button
              size="sm"
              disabled={source === null}
              onClick={() => {
                if (source !== null) {
                  save(source, fileName);
                }
              }}
            >
              <Download size={14} aria-hidden="true" />
              Download .typ
            </Button>
          </div>

          {rendered.error !== null ? (
            <p className={styles.fragmentProblem}>{typstProblem(rendered.error)}</p>
          ) : null}

          {source === null ? (
            <div
              className={styles.sourceWait}
              role="status"
              aria-label="Writing the source"
              aria-busy="true"
            >
              <span className={styles.paperBar} />
              <span className={styles.paperBar} />
              <span className={styles.paperBar} />
            </div>
          ) : (
            <div className={styles.code}>
              <pre className={styles.gutter} aria-hidden="true">
                {lines.map((_, index) => String(index + 1)).join("\n")}
              </pre>
              <pre
                className={styles.codeText}
                aria-label={`${fileName}, as Typst`}
                title="Generated from the structure every time — edit the questions, not this"
                tabIndex={0}
              >
                {source}
              </pre>
            </div>
          )}
        </div>

        <div className={styles.sourcePane}>
          <div className={styles.preview}>
            <FragmentView
              body={{ kind: "paper", document: structure, output: "svg" }}
              label="the paper"
              empty="Nothing to set yet."
            />
          </div>
        </div>
      </div>
    </>
  );
}
