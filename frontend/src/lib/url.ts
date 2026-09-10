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

/**
 * The shareable URL for a pick: /p/<id> on this site. The static host rewrites
 * it to the API, which serves the pick's own link-preview tags and card; if the
 * rewrite is not configured, the 404 page forwards people to the pick instead.
 */
export function permalinkFor(hourlyId: string): string {
  if (typeof window === "undefined") return `/p/${hourlyId}`;
  return `${window.location.origin}/p/${hourlyId}`;
}

export function xShareUrl(text: string, url: string): string {
  return `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
}

export function blueskyShareUrl(text: string, url: string): string {
  return `https://bsky.app/intent/compose?text=${encodeURIComponent(`${text} ${url}`)}`;
}

/** The pick id requested by the current URL, if any. */
export function readPickParam(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("pick");
}
