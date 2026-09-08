"use client";

import { useState } from 'react';

/**
 * An image that is never an empty box.
 *
 * Falls back to `fallback` when there is no image URL *and* when the image fails
 * to load -- publishers rewrite and expire og:image URLs, so a stored link going
 * dead is normal, not exceptional.
 *
 * A real <img> rather than a CSS background so it carries a text alternative
 * (WCAG 1.1.1). next/image is not used because a static export cannot optimise
 * arbitrary remote hosts.
 */
export default function Thumbnail({
  src,
  alt,
  fallback,
  className,
  style,
}: {
  src?: string | null;
  alt: string;
  fallback: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  // Storing the failed URL (rather than a boolean) resets automatically when a
  // different image is passed in, with no effect needed.
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const usable = src && failedSrc !== src;

  return (
    <div
      className={`relative overflow-hidden ${className || ""}`}
      style={{ background: 'var(--sunken)', ...style }}
    >
      {usable ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          onError={() => setFailedSrc(src)}
          className="absolute inset-0 w-full h-full"
          style={{ objectFit: 'cover' }}
          loading="lazy"
        />
      ) : (
        <div className="absolute inset-0" style={{ background: 'var(--accent-wash)' }}>
          {fallback}
        </div>
      )}
    </div>
  );
}
