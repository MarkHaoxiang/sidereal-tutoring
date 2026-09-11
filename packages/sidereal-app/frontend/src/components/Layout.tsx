import { Outlet } from "react-router-dom";

import { TopNav } from "./TopNav";
import styles from "./Layout.module.css";

export function Layout() {
  return (
    <div className={styles.shell}>
      <TopNav />
      <main className={styles.content}>
        <Outlet />
      </main>
    </div>
  );
}
