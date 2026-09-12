import { useFileBlob } from "@/lib/files";

import styles from "./account.module.css";

/** The letters shown while there is no photo: one from each of the first two words. */
function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase());
  return letters.join("") || "?";
}

export function Avatar({ name, fileId }: { name: string; fileId: string | null }) {
  const photo = useFileBlob(fileId, "Your photo");

  if (photo.url) {
    return (
      <span className={styles.avatar}>
        <img src={photo.url} alt="Your photo" className={styles.avatarImage} />
      </span>
    );
  }

  return (
    <span className={styles.avatar} role="img" aria-label="No photo yet">
      {initials(name)}
    </span>
  );
}
