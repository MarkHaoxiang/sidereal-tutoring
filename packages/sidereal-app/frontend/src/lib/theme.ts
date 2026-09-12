import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";
/** What was chosen: one of the two themes, or "auto" to follow the device. */
export type Appearance = Theme | "auto";

const STORAGE_KEY = "sidereal-theme";
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

function readStoredAppearance(): Appearance | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" || stored === "auto" ? stored : null;
  } catch {
    return null;
  }
}

// One module-level store rather than per-component state: the toggle, the account page
// and anything that has to follow the theme (the toast layer, for one) must see the
// same value. localStorage carries it before a user is known and while none is.
let appearance: Appearance = readStoredAppearance() ?? "auto";
let writeToAccount: ((next: Appearance) => void) | null = null;
const listeners = new Set<() => void>();

function resolved(): Theme {
  if (appearance === "auto") {
    return prefersDark.matches ? "dark" : "light";
  }
  return appearance;
}

function apply() {
  document.body.dataset["theme"] = resolved();
  try {
    localStorage.setItem(STORAGE_KEY, appearance);
  } catch {
    // Best-effort only — a private window or blocked storage should not break the toggle.
  }
}

function announce() {
  for (const listener of listeners) {
    listener();
  }
}

apply();

// The device can change its mind while the app is open, and "auto" has to follow it.
prefersDark.addEventListener("change", () => {
  if (appearance === "auto") {
    apply();
    announce();
  }
});

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The signed-in account's own value: applied and remembered, never written back. */
export function adoptAppearance(next: Appearance) {
  appearance = next;
  apply();
  announce();
}

/** A choice just made here: applied, and saved to the account when one is signed in. */
export function setAppearance(next: Appearance) {
  adoptAppearance(next);
  writeToAccount?.(next);
}

/** Where a choice is saved while someone is signed in; null leaves localStorage with it alone. */
export function setAppearanceWriter(writer: ((next: Appearance) => void) | null) {
  writeToAccount = writer;
}

export function useAppearance(): [Appearance, (next: Appearance) => void] {
  const current = useSyncExternalStore(
    subscribe,
    () => appearance,
    () => appearance
  );
  return [current, setAppearance];
}

export function useTheme(): [Theme, () => void] {
  const current = useSyncExternalStore(subscribe, resolved, resolved);
  const toggle = useCallback(() => {
    setAppearance(resolved() === "dark" ? "light" : "dark");
  }, []);
  return [current, toggle];
}
