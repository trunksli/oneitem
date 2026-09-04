"use client";

import { API_BASE } from '@/lib/api';

/**
 * Shown when the API cannot be reached.
 *
 * Without this, an outage rendered as normal curation: the fetch failed, the
 * page fell through to its empty state, and the site cheerfully claimed it was
 * "discovering something amazing" while actually being down.
 */
export default function ApiWarning({ failed = false }: { failed?: boolean }) {
  if (!failed) return null;

  return (
    <div
      className="w-full px-6 md:px-10 py-3"
      style={{ background: 'var(--danger)', color: '#FFF8F4' }}
    >
      <p className="label">Cannot reach the API</p>
      <p className="text-sm mt-1">
        Nothing can load right now. The site is trying <code>{API_BASE}</code>.
        If that address is wrong, set <code>NEXT_PUBLIC_API_URL</code> on the static
        site and redeploy &mdash; it is baked in at build time, so saving it alone
        will not take effect.
      </p>
    </div>
  );
}
