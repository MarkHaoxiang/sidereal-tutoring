import { Toaster } from "sonner";

import { useTheme } from "@/lib/theme";
import { holdToasts } from "@/lib/toplayer";

import styles from "./Toasts.module.css";

// Sonner renders outside the React tree with its own inline styles, so the tokens have
// to be handed to it explicitly; both shells use this rather than repeating them.
export function Toasts() {
  const [theme] = useTheme();

  return (
    <div ref={holdToasts} className={styles.host}>
      <Toaster
        theme={theme}
        position="bottom-right"
        toastOptions={{
          style: {
            background: "var(--color-bg-raised)",
            color: "var(--color-fg)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-card)",
            boxShadow: "var(--shadow-lifted)",
            fontFamily: "var(--font-sans)",
            fontSize: "var(--font-size-body)",
          },
        }}
      />
    </div>
  );
}
