import Link from 'next/link';
import { CONTACT_EMAIL, LAST_UPDATED, SITE_NAME, type LegalSection } from '@/lib/legal';

/**
 * Shared shell for the legal routes, so Terms and Privacy cannot drift apart in
 * layout or navigation. A server component: the text is static, so it ships as
 * plain HTML with no JavaScript.
 */

function slug(heading: string): string {
  return heading.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// URLs and the contact address in the copy become real links. Trailing
// punctuation is kept outside the link, so "...terms." links "terms" not "terms.".
const LINKABLE = /(https?:\/\/[^\s]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g;

function withLinks(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(LINKABLE)) {
    const raw = match[0];
    const start = match.index ?? 0;
    const trimmed = raw.replace(/[.,;:)]+$/, "");
    out.push(text.slice(last, start));
    const href = trimmed.includes("@") && !trimmed.startsWith("http") ? `mailto:${trimmed}` : trimmed;
    out.push(
      <a key={start} href={href} className="link-accent"
         {...(href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
        {trimmed}
      </a>
    );
    last = start + trimmed.length;
  }
  out.push(text.slice(last));
  return out;
}

export default function LegalPage({
  title,
  intro,
  sections,
  other,
}: {
  title: string;
  intro?: string;
  sections: LegalSection[];
  other: { href: string; label: string };
}) {
  return (
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
      <header
        className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
        style={{ borderBottom: '2px solid var(--rule)' }}
      >
        <Link href="/" className="display text-2xl font-bold tracking-tight leading-none"
              style={{ color: 'var(--ink)', textDecoration: 'none' }}>
          {SITE_NAME}
        </Link>
        <Link href="/" className="label link-accent">Now Playing &#8594;</Link>
      </header>

      <article className="mx-auto px-6 md:px-10 py-10 md:py-16" style={{ maxWidth: 'var(--content-max)' }}>
        <p className="label" style={{ color: 'var(--ink-faint)' }}>
          {SITE_NAME} &middot; Last updated {LAST_UPDATED}
        </p>
        <h1 className="display mt-3 text-3xl md:text-4xl leading-tight">{title}</h1>
        {intro && (
          <p className="mt-4 text-[17px] leading-relaxed" style={{ color: 'var(--ink-muted)' }}>{intro}</p>
        )}

        <nav aria-label="Contents" className="mt-8 pt-6" style={{ borderTop: '1px solid var(--line)' }}>
          <p className="label" style={{ color: 'var(--ink-faint)' }}>Contents</p>
          <ol className="mt-3 flex flex-col gap-1 text-[15px]">
            {sections.map(section => (
              <li key={section.heading}>
                <a href={`#${slug(section.heading)}`} className="link-accent">{section.heading}</a>
              </li>
            ))}
          </ol>
        </nav>

        {sections.map(section => (
          <section key={section.heading} id={slug(section.heading)} className="mt-10"
                   style={{ scrollMarginTop: 24 }}>
            <h2 className="display text-xl md:text-2xl leading-snug">{section.heading}</h2>
            {section.body.map((paragraph, i) => (
              <p key={i} className="mt-3 text-[16px] leading-relaxed">{withLinks(paragraph)}</p>
            ))}
          </section>
        ))}

        <div className="mt-14 pt-6 flex flex-wrap gap-x-6 gap-y-2 justify-between"
             style={{ borderTop: '1px solid var(--line)' }}>
          <Link href={other.href} className="label link-accent">{other.label} &#8594;</Link>
          <a href={`mailto:${CONTACT_EMAIL}`} className="label link-accent">{CONTACT_EMAIL}</a>
        </div>
      </article>
    </main>
  );
}
