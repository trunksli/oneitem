"use client";

import { useSyncExternalStore } from 'react';
import { isApiMisconfigured } from '@/lib/api';

const noopSubscribe = () => () => {};

/**
 * Shown when the site was built without NEXT_PUBLIC_API_URL, which otherwise
 * fails silently: the developer's own browser reaches their local dev server, so
 * the deployment looks fine to them while being broken for everyone else.
 *
 * The check needs the hostname, so it is client-only; the server snapshot is
 * false to keep the prerendered HTML and first client render in agreement.
 */
export default function ApiWarning() {
  const broken = useSyncExternalStore(
    noopSubscribe,
    () => isApiMisconfigured(),
    () => false,
  );

  if (!broken) return null;

  return (
    <div
      className="w-full px-6 md:px-10 py-3"
      style={{ background: 'var(--danger)', color: '#FFF8F4' }}
    >
      <p className="label">API not configured</p>
      <p className="text-sm mt-1">
        This build has no <code>NEXT_PUBLIC_API_URL</code>, so it cannot load content.
        Set it on the static site to the API&apos;s URL and redeploy &mdash; it is baked
        in at build time, so a restart alone will not pick it up.
      </p>
    </div>
  );
}
