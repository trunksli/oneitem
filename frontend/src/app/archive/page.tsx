"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { safeExternalUrl } from '@/lib/url';
import { API_BASE } from '@/lib/api';
import ApiWarning from '@/components/api-warning';
import Thumbnail from '@/components/thumbnail';


interface ArchiveEntry {
  hourly_id: string;
  publish_time: string;
  theme: string;
  editorial_explanation: string | null;
  title: string | null;
  creator_name: string | null;
  url: string | null;
  thumbnail_url: string | null;
  source_type: string | null;
  preview_text?: string | null;
  tone?: string | null;
}

function formatHour(publishTime: string): string {
  // Stored as UTC ("YYYY-MM-DDTHH:MM:SS"); rendered in the viewer's timezone.
  const date = new Date(publishTime.replace(" ", "T").split(".")[0] + "Z");
  if (isNaN(date.getTime())) return publishTime;
  return date.toLocaleString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric'
  });
}

export default function Archive() {
  const [entries, setEntries] = useState<ArchiveEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/archive`)
      .then(res => res.json())
      .then(data => {
        setEntries(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoadFailed(true);
        setLoading(false);
      });
  }, []);

  return (
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
      <ApiWarning failed={loadFailed} />


      <header
        className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
        style={{ borderBottom: '2px solid var(--rule)' }}
      >
        <Link href="/" className="display text-2xl font-bold tracking-tight leading-none" style={{ color: 'var(--ink)', textDecoration: 'none' }}>
          ONE
        </Link>
        <Link href="/" className="label link-accent">Now Playing &#8594;</Link>
      </header>

      <div className="mx-auto px-6 md:px-10 py-10 md:py-16" style={{ maxWidth: 'var(--content-max)' }}>
        <p className="label" style={{ color: 'var(--ink-faint)' }}>The Archive</p>
        <h1 className="display mt-3 text-3xl md:text-4xl leading-tight">Past Diamonds</h1>
        <p className="mt-2 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
          Every hour we have featured, newest first.
        </p>

        <div className="mt-10 flex flex-col">
          {loading ? (
            <p className="label" style={{ color: 'var(--ink-faint)' }}>Loading</p>
          ) : entries.length === 0 ? (
            <p className="text-[15px]" style={{ color: 'var(--ink-muted)' }}>
              Nothing has been featured yet. Check back after the first hour.
            </p>
          ) : (
            entries.map(entry => (
              <Link
                key={entry.hourly_id}
                href={`/?pick=${entry.hourly_id}`}
                className="flex gap-5 items-start py-6"
                style={{ borderBottom: '1px solid var(--line)', textDecoration: 'none', color: 'inherit' }}
              >
                <Thumbnail
                  src={entry.thumbnail_url}
                  alt={entry.title || ""}
                  className="w-28 h-[63px] md:w-40 md:h-[90px] shrink-0"
                  style={{ border: '1px solid var(--line-strong)' }}
                  fallback={
                    <div className="h-full flex items-center justify-center px-2">
                      <span className="label text-center" style={{ color: 'var(--accent)' }}>
                        {entry.tone || entry.theme || "Reading"}
                      </span>
                    </div>
                  }
                />
                <div className="min-w-0">
                  <p className="label" style={{ color: 'var(--accent)' }}>
                    {formatHour(entry.publish_time)} / {(entry.theme || "").replace(/_/g, " ")}
                  </p>
                  <h2 className="display text-lg md:text-xl leading-snug mt-1">
                    {entry.title || "(removed)"}
                  </h2>
                  <p className="text-sm mt-1" style={{ color: 'var(--ink-muted)' }}>
                    {entry.creator_name}
                  </p>
                  {(entry.preview_text || entry.editorial_explanation) && (
                    <p className="text-[15px] mt-2 leading-relaxed" style={{ color: 'var(--ink-faint)' }}>
                      {(entry.preview_text || entry.editorial_explanation || "").slice(0, 200)}
                    </p>
                  )}
                  {safeExternalUrl(entry.url) && (
                    <span
                      className="label link-accent inline-block mt-3"
                      role="link"
                      tabIndex={0}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        window.open(safeExternalUrl(entry.url), "_blank", "noopener,noreferrer");
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          e.stopPropagation();
                          window.open(safeExternalUrl(entry.url), "_blank", "noopener,noreferrer");
                        }
                      }}
                    >
                      Open the original &#8599;
                    </span>
                  )}
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </main>
  );
}
