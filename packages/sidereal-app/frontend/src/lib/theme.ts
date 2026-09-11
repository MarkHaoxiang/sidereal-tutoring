import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "sidereal-theme";

function readStoredTheme(): Theme | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : null;
  } catch {
    return null;
  }
}

// One module-level store rather than per-component state: the toggle and anything that
// has to follow the theme (the toast layer, for one) must see the same value.
let theme: Theme = readStoredTheme() ?? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const listeners = new Set<() => void>();

function apply() {
  document.body.dataset["theme"] = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Best-effort only — a private window or blocked storage should not break the toggle.
  }
}

apply();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setTheme(next: Theme) {
  theme = next;
  apply();
  for (const listener of listeners) {
    listener();
  }
}

export function useTheme(): [Theme, () => void] {
  const current = useSyncExternalStore(
    subscribe,
    () => theme,
    () => theme
  );
  const toggle = useCallback(() => {
    setTheme(theme === "dark" ? "light" : "dark");
  }, []);
  return [current, toggle];
}
