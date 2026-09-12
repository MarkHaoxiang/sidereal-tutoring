import { Outlet } from "react-router-dom";

import { Toasts } from "@/components/Toasts";

import { StudentNav } from "./StudentNav";
import styles from "./StudentLayout.module.css";

export function StudentLayout() {
  return (
    <div className={styles.shell}>
      <StudentNav />
      <main className={styles.content}>
        <Outlet />
      </main>
      <Toasts />
    </div>
  );
}
