"use client";

import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
}

function formatHour(publishTime: string): string {
  // Stored as UTC "YYYY-MM-DD HH:MM:SS.ffffff"; render in the viewer's timezone
  const date = new Date(publishTime.replace(" ", "T").split(".")[0] + "Z");
  if (isNaN(date.getTime())) return publishTime;
  return date.toLocaleString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric'
  });
}

export default function Archive() {
  const [entries, setEntries] = useState<ArchiveEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/archive`)
      .then(res => res.json())
      .then(data => {
        setEntries(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <main className="min-h-screen bg-[#FDFDFD] text-[#111111] font-sans p-6 md:p-16">
      <header className="max-w-3xl mx-auto mb-12 flex justify-between items-end">
        <div>
          <a href="/" className="text-xl font-bold tracking-tighter hover:text-gray-500 transition-colors">ONE</a>
          <h1 className="text-3xl md:text-4xl font-medium tracking-tight mt-2">Past Diamonds</h1>
          <p className="text-sm text-gray-500 mt-1">Every hour&apos;s featured pick, newest first.</p>
        </div>
        <a href="/" className="text-sm font-bold tracking-widest uppercase hover:text-gray-500 transition-colors">
          Now Playing →
        </a>
      </header>

      <div className="max-w-3xl mx-auto flex flex-col gap-8">
        {loading ? (
          <div className="text-gray-400 italic">Loading the archive...</div>
        ) : entries.length === 0 ? (
          <div className="text-gray-400 italic">Nothing featured yet — check back after the first hour.</div>
        ) : (
          entries.map(entry => (
            <a
              key={entry.hourly_id}
              href={entry.url ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex gap-5 items-start border-b border-gray-200 pb-8"
            >
              <div
                className="w-32 h-20 md:w-44 md:h-28 bg-gray-100 border border-gray-200 shrink-0"
                style={entry.thumbnail_url ? {
                  backgroundImage: `url(${entry.thumbnail_url})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center'
                } : {}}
              />
              <div className="min-w-0">
                <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                  {formatHour(entry.publish_time)} &middot; {(entry.theme || "").replace(/_/g, " ")}
                </div>
                <h2 className="text-lg md:text-xl font-medium leading-snug mt-1 group-hover:text-gray-500 transition-colors">
                  {entry.title || "(removed)"}
                </h2>
                <div className="text-sm text-gray-500 mt-1">{entry.creator_name}</div>
                {entry.editorial_explanation && (
                  <p className="text-sm text-gray-600 font-serif italic mt-2 line-clamp-2">
                    {entry.editorial_explanation}
                  </p>
                )}
              </div>
            </a>
          ))
        )}
      </div>
    </main>
  );
}
