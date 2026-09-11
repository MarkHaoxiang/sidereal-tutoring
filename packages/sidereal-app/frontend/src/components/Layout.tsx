import { Toaster } from "sonner";
import { Outlet } from "react-router-dom";

import { useTheme } from "@/lib/theme";

import { TopNav } from "./TopNav";
import styles from "./Layout.module.css";

export function Layout() {
  const [theme] = useTheme();

  return (
    <div className={styles.shell}>
      <TopNav />
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
