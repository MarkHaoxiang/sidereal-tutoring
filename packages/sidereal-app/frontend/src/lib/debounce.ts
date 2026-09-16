import { useEffect, useState } from "react";

/**
 * `value` once `key` has stopped changing for `delay` ms. `key` is what identifies the
 * value — its JSON, a hash — so a value rebuilt on every render settles all the same.
 */
export function useDebounced<T>(value: T, key: string, delay: number): T {
  const [settled, setSettled] = useState({ key, value });

  useEffect(() => {
    if (settled.key === key) {
      return;
    }
    const timer = setTimeout(() => {
      setSettled({ key, value });
    }, delay);
    return () => {
      clearTimeout(timer);
    };
  }, [key, value, delay, settled.key]);

  return settled.value;
}
