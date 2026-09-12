import { useCallback, useMemo, useSyncExternalStore } from "react";

/**
 * Tracks a media query. The tutor shell renders either the sidebar or the top bar —
 * never both behind `display: none`, which would put two "Main" navigations in the
 * accessibility tree.
 */
export function useMediaQuery(query: string): boolean {
  const list = useMemo(() => window.matchMedia(query), [query]);

  const subscribe = useCallback(
    (listener: () => void) => {
      list.addEventListener("change", listener);
      return () => {
        list.removeEventListener("change", listener);
      };
    },
    [list]
  );

  return useSyncExternalStore(
    subscribe,
    () => list.matches,
    () => false
  );
}
