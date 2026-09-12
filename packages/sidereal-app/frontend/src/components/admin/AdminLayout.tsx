import { Outlet } from "react-router-dom";

import { Toasts } from "@/components/Toasts";
import { cx } from "@/lib/cx";
import { useMediaQuery } from "@/lib/media";

import { AdminNav } from "./AdminNav";
import styles from "./AdminLayout.module.css";

const WIDE = "(min-width: 64rem)";

export function AdminLayout() {
  const wide = useMediaQuery(WIDE);

  return (
    <div className={cx(styles.shell, wide && styles.wide)}>
      {wide ? (
        <aside className={styles.aside}>
          <AdminNav variant="sidebar" />
        </aside>
      ) : (
        <AdminNav variant="top" />
      )}
      <main className={styles.content}>
        <Outlet />
      </main>
      <Toasts />
    </div>
  );
}
