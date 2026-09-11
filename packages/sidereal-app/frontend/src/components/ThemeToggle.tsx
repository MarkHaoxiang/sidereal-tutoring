import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/lib/theme";

import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  const [theme, toggle] = useTheme();

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
    >
      {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
