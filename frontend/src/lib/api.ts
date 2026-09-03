/**
 * Where the browser should call the API.
 *
 * NEXT_PUBLIC_API_URL is inlined at BUILD time, so it must be set on the static
 * site before the build runs; setting it afterwards does nothing until a redeploy.
 *
 * The old code fell back to http://localhost:8000 unconditionally. That failure is
 * uniquely nasty: on the developer's own machine the deployed site appears to work,
 * because their browser reaches their own dev server -- while every other visitor
 * gets a site that can never load anything. So the fallback now applies only when
 * the page is itself being served from localhost. Anywhere else, a missing value is
 * treated as a misconfiguration and surfaced in the UI.
 */
const CONFIGURED = process.env.NEXT_PUBLIC_API_URL;

function resolveApiBase(): string {
  if (CONFIGURED) return CONFIGURED;
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "localhost" && host !== "127.0.0.1") return "";
  }
  return "http://localhost:8000";
}

export const API_BASE: string = resolveApiBase();

/** True when the site is deployed but was built without an API URL. */
export function isApiMisconfigured(): boolean {
  return resolveApiBase() === "";
}
