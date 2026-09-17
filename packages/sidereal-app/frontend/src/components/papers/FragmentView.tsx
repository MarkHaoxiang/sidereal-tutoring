import { useRenderAssets, useRenderTypst } from "@/lib/queries";
import type { RenderBody } from "@/lib/queries";
import { typstProblem } from "@/lib/typeset";

import styles from "./papers.module.css";

export interface FragmentViewProps {
  /** Null while the draft is too incomplete to send; `empty` stands in for it. */
  body: RenderBody | null;
  /** What is being set, for the wait's label: "question 3". */
  label: string;
  empty: string;
}

/** A canonical fragment as the typeset service sets it, on the paper it will be printed on. */
export function FragmentView({ body, label, empty }: FragmentViewProps) {
  const rendered = useRenderTypst(useRenderAssets(body));
  const pages = rendered.data?.pages ?? [];
  const problem = rendered.error === null ? null : typstProblem(rendered.error);

  if (body === null) {
    return <p className={styles.status}>{empty}</p>;
  }

  return (
    <div className={styles.fragment}>
      <div className={styles.paper}>
        {pages.length > 0 ? (
          pages.map((page, index) => (
            // The SVG comes from this app's own typeset service, which compiles in a world
            // with no files, no packages and no network.
            <div
              key={index}
              className={styles.paperPage}
              dangerouslySetInnerHTML={{ __html: page }}
            />
          ))
        ) : problem !== null ? (
          <p className={styles.paperBlank}>Nothing was set.</p>
        ) : (
          <div className={styles.paperWait} role="status" aria-label={`Setting ${label}`} aria-busy="true">
            <span className={styles.paperBar} />
            <span className={styles.paperBar} />
            <span className={styles.paperBar} />
          </div>
        )}
      </div>
      {problem !== null ? <p className={styles.fragmentProblem}>{problem}</p> : null}
    </div>
  );
}
