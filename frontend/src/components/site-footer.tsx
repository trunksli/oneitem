import Link from 'next/link';

/**
 * Site-wide footer: the legal links, and the standing disclosure that previews
 * are AI-written. Server component -- static markup, no JavaScript.
 */
export default function SiteFooter() {
  return (
    <footer className="w-full px-6 md:px-10 py-8 mt-16" style={{ borderTop: '1px solid var(--line)' }}>
      <div className="mx-auto flex flex-wrap gap-x-6 gap-y-3 items-center justify-between"
           style={{ maxWidth: 'var(--content-max)' }}>
        <p className="text-sm" style={{ color: 'var(--ink-faint)' }}>
          Previews are written by AI and can be wrong. The original is always one click away.
        </p>
        <nav aria-label="Legal" className="flex gap-5">
          <Link href="/privacy" className="label link-accent">Privacy</Link>
          <Link href="/terms" className="label link-accent">Terms</Link>
        </nav>
      </div>
    </footer>
  );
}
