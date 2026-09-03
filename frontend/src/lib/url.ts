/**
 * Defence in depth for third-party links.
 *
 * The API already drops non-http(s) URLs, but content originates in RSS feeds and
 * the YouTube API, so the browser validates again before a value reaches an href
 * or window.open() -- where a `javascript:` URL would execute on click.
 */
export function safeExternalUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  const trimmed = url.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return undefined;
}

/** The shareable URL for a featured hour. */
export function permalinkFor(hourlyId: string): string {
  if (typeof window === "undefined") return `/?pick=${hourlyId}`;
  return `${window.location.origin}/?pick=${hourlyId}`;
}

/** The pick id requested by the current URL, if any. */
export function readPickParam(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("pick");
}
