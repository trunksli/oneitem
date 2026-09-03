"use client";

import { useCallback, useState, useSyncExternalStore } from 'react';

const noopSubscribe = () => () => {};

/**
 * A string value backed by localStorage.
 *
 * Uses useSyncExternalStore rather than reading storage in an effect: the server
 * snapshot is the empty string, so the prerendered HTML and the first client
 * render agree, and there is no setState-in-effect cascade. Storage access is
 * wrapped because private mode and blocked site data make it throw.
 */
export function usePersistentState(key: string, initial = "") {
  const stored = useSyncExternalStore(
    noopSubscribe,
    () => {
      try {
        return localStorage.getItem(key) ?? initial;
      } catch {
        return initial;
      }
    },
    () => initial,
  );

  // Edits live in React state; storage is only the seed and the durable copy.
  const [edited, setEdited] = useState<string | null>(null);
  const value = edited ?? stored;

  const set = useCallback((next: string) => {
    setEdited(next);
    try {
      localStorage.setItem(key, next);
    } catch { /* storage unavailable - the value simply will not persist */ }
  }, [key]);

  return [value, set] as const;
}
