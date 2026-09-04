/**
 * Where the browser should call the API.
 *
 * Resolution order:
 *   1. NEXT_PUBLIC_API_URL, inlined at BUILD time (must be set before the build
 *      runs; setting it afterwards does nothing until a redeploy).
 *   2. The known production API, when the page is served from anywhere that is
 *      not localhost.
 *   3. localhost:8000, for local development.
 *
 * Step 2 exists because step 1 has silently failed twice in deployment, and its
 * failure mode is the worst kind: the old code fell back to localhost:8000
 * unconditionally, so the deployed site appeared to work on the developer's own
 * machine (their browser reached their own dev server) while being completely
 * broken for every other visitor. The API URL is public, not a secret, so
 * hardcoding a default costs nothing and makes the deployment self-healing.
 * The environment variable still wins whenever it is set, so other environments
 * (staging, a renamed service) need no code change.
 */
const CONFIGURED = process.env.NEXT_PUBLIC_API_URL;

const PRODUCTION_API = "https://one-api-lcrh.onrender.com";

function isLocalHost(host: string): boolean {
  return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
}

function resolveApiBase(): string {
  if (CONFIGURED) return CONFIGURED;
  if (typeof window !== "undefined" && !isLocalHost(window.location.hostname)) {
    return PRODUCTION_API;
  }
  return "http://localhost:8000";
}

export const API_BASE: string = resolveApiBase();

/** True only if we somehow have no usable base at all. */
export function isApiMisconfigured(): boolean {
  return !resolveApiBase();
}
