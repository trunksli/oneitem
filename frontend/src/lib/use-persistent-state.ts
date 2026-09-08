"use client";

import { useCallback, useState, useSyncExternalStore } from 'react';

const noopSubscribe = () => () => {};

// Module level, so it never changes identity and never needs to be a dependency.
function storeFor(kind: "local" | "session"): Storage {
  return kind === "local" ? localStorage : sessionStorage;
}

/**
 * A string value backed by localStorage.
 *
 * Uses useSyncExternalStore rather than reading storage in an effect: the server
 * snapshot is the empty string, so the prerendered HTML and the first client
 * render agree, and there is no setState-in-effect cascade. Storage access is
 * wrapped because private mode and blocked site data make it throw.
 */
export function usePersistentState(key: string, initial = "") {
  return useStorageState("local", key, initial);
}

/**
 * The same, backed by sessionStorage: the value dies with the tab. Used for the
 * admin session token, which should not outlive the browsing session the way a
 * localStorage value would.
 */
export function useSessionState(key: string, initial = "") {
  return useStorageState("session", key, initial);
}

// `kind` rather than a getter function: an inline arrow would change identity on
// every render, making the returned setter unstable and re-triggering any effect
// that depends on it.
function useStorageState(kind: "local" | "session", key: string, initial: string) {
  const stored = useSyncExternalStore(
    noopSubscribe,
    () => {
      try {
        return storeFor(kind).getItem(key) ?? initial;
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
      if (next) storeFor(kind).setItem(key, next);
      else storeFor(kind).removeItem(key);
    } catch { /* storage unavailable - the value simply will not persist */ }
  }, [kind, key]);

  return [value, set] as const;
}
