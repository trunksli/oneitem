"use client";

import { useSyncExternalStore } from 'react';
import { readPickParam } from '@/lib/url';

const noopSubscribe = () => () => {};

/**
 * The ?pick=<id> value from the URL, read without a setState-in-effect cascade.
 * The server snapshot is null so the prerendered HTML matches the first client
 * render; static export means the query string is only ever known in the browser.
 */
export function usePickParam(): string | null {
  return useSyncExternalStore(noopSubscribe, readPickParam, () => null);
}
