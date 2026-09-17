import { Link } from "react-router-dom";

import styles from "./artefacts.module.css";

export interface TypstSourceProps {
  content: string;
  /** The paper this sheet was cut from. */
  paperId: string;
}

/**
 * A worksheet's source, read rather than edited: it names the figure and table files the paper
 * carries, which a recompile on its own cannot supply. Changing it would print the sheet
 * without them, so the paper is where a change belongs.
 */
export function TypstSource({ content, paperId }: TypstSourceProps) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Content</h2>
      </div>
      <p className={styles.sectionNote}>
        Cut from <Link to={`/library/papers/${paperId}`}>the paper</Link>. Edit it there and set the
        worksheet again.
      </p>
      <pre className={styles.source}>{content}</pre>
    </section>
  );
}
