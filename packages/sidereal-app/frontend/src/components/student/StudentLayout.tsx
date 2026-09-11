import { Toaster } from "sonner";
import { Outlet } from "react-router-dom";

import { useTheme } from "@/lib/theme";

import { StudentNav } from "./StudentNav";
import styles from "./StudentLayout.module.css";

export function StudentLayout() {
  const [theme] = useTheme();

  return (
    <div className={styles.shell}>
      <StudentNav />
      <main className={styles.content}>
        <Outlet />
      </main>
      <Toaster
        theme={theme}
        position="bottom-right"
        toastOptions={{
          style: {
            background: "var(--color-bg-raised)",
            color: "var(--color-fg)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-card)",
          },
        }}
      />
    </div>
  );
}
