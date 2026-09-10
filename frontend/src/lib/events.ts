import { API_BASE } from '@/lib/api';

export type EventType =
  | "view"
  | "play"
  | "read"
  | "open_original"
  | "copy_link"
  | "share_x"
  | "share_bluesky"
  | "share_native";

/**
 * Report an anonymous engagement event. Fire-and-forget.
 *
 * Nothing identifying is sent -- no cookie, no ID. The server derives a
 * daily-salted hash from the request itself and destroys the salt each day, so
 * it can count "one view per person per day" without knowing who anyone is.
 *
 * keepalive lets the request finish even when the click navigates away, as it
 * does when someone opens the original article.
 */
export function track(hourlyId: string | null | undefined, type: EventType): void {
  if (!hourlyId) return;
  try {
    void fetch(`${API_BASE}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hourly_one_id: hourlyId, event_type: type }),
      keepalive: true,
    }).catch(() => { /* measurement must never break the page */ });
  } catch {
    /* measurement must never break the page */
  }
}
