import { Outlet } from "react-router-dom";

import { cx } from "@/lib/cx";
import { useMediaQuery } from "@/lib/media";

import { Sidebar } from "./Sidebar";
import { Toasts } from "./Toasts";
import { TopNav } from "./TopNav";
import styles from "./Layout.module.css";

// One nav at a time: the sidebar above 64rem, the top bar with its menu below it.
const WIDE = "(min-width: 64rem)";

export function Layout() {
  const wide = useMediaQuery(WIDE);

  return (
    <div className={cx(styles.shell, wide && styles.wide)}>
      {wide ? (
        <aside className={styles.aside}>
          <Sidebar />
        </aside>
      ) : (
        <TopNav />
      )}
      <main className={styles.content}>
        <Outlet />
      </main>
      <Toasts />
    </div>
  );
}
