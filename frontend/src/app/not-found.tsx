"use client";

import Link from 'next/link';
import { useEffect, useSyncExternalStore } from 'react';

const noopSubscribe = () => () => {};

/** A share link (/p/<id>) that reached this page instead of the API. */
function sharedPickId(): string | null {
  const match = window.location.pathname.match(/^\/p\/([A-Za-z0-9-]{1,64})\/?$/);
  return match ? match[1] : null;
}

/**
 * Exported as 404.html, which the static host serves for any unknown path.
 *
 * Share links are /p/<id>, normally rewritten to the API. If that rewrite is not
 * configured yet, the link lands here -- so rather than a dead end, forward to
 * the pick itself. People arrive where they meant to; only the rich preview for
 * crawlers depends on the rewrite.
 */
export default function NotFound() {
  const pickId = useSyncExternalStore(noopSubscribe, sharedPickId, () => null);

  useEffect(() => {
    if (pickId) window.location.replace(`/?pick=${pickId}`);
  }, [pickId]);

  return (
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
      <header className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
              style={{ borderBottom: '2px solid var(--rule)' }}>
        <Link href="/" className="display text-2xl font-bold tracking-tight leading-none"
              style={{ color: 'var(--ink)', textDecoration: 'none' }}>ONE</Link>
        <Link href="/" className="label link-accent">Now Playing &#8594;</Link>
      </header>
      <div className="mx-auto px-6 md:px-10 py-16" style={{ maxWidth: 'var(--content-max)' }}>
        {pickId ? (
          <p className="label" style={{ color: 'var(--ink-faint)' }}>Opening the pick&hellip;</p>
        ) : (
          <>
            <p className="label" style={{ color: 'var(--ink-faint)' }}>404</p>
            <h1 className="display mt-3 text-3xl md:text-4xl">This page isn&apos;t here.</h1>
            <p className="mt-3 text-[17px]" style={{ color: 'var(--ink-muted)' }}>
              The current pick is, though. So is everything we have featured before.
            </p>
            <div className="mt-6 flex gap-5">
              <Link href="/" className="label link-accent">The current pick &#8594;</Link>
              <Link href="/archive" className="label link-accent">The archive &#8594;</Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
