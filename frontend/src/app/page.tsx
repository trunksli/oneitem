"use client";

import { useState, useEffect, useCallback, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { Play, BookOpen, Headphones, Link2, Check } from 'lucide-react';
import { API_BASE } from '@/lib/api';
import ApiWarning from '@/components/api-warning';
import Thumbnail from '@/components/thumbnail';
import Countdown from '@/components/countdown';
import { usePersistentState } from '@/lib/use-persistent-state';
import { safeExternalUrl, permalinkFor, xShareUrl, blueskyShareUrl } from '@/lib/url';
import { usePickParam } from '@/lib/use-pick-param';
import { track } from '@/lib/events';


interface Candidate {
  id?: string;
  url?: string;
  source_id?: string;
  source_type: string;
  title: string;
  creator_name: string;
  creator_url?: string;
  ai_explanation: string;
  thumbnail_url: string;
  preview_text?: string | null;
  tone?: string | null;
}

const SOURCE_LABELS: Record<string, string> = {
  YOUTUBE: "YouTube", VIMEO: "Vimeo", PODCAST: "Podcast", RSS: "Article", WEB: "Web",
};

interface HourlyResponse {
  hourly?: { id: string; theme: string; publish_time?: string };
  candidate?: Candidate;
  is_stale?: boolean;
  is_permalink?: boolean;
  next_publish_time?: string;
}

const noopSubscribe = () => () => {};

export default function Home() {
  const [hourlyOne, setHourlyOne] = useState<HourlyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  // Answers remembered on this device only, so the chosen one shows and can be changed.
  const [votesJson, setVotesJson] = usePersistentState("one_votes");
  const [copied, setCopied] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  // A ?pick=<id> URL pins the page to one archived hour instead of "now".
  const pinnedId = usePickParam();
  // The device's own share sheet, where the browser offers one (mostly mobile).
  const canNativeShare = useSyncExternalStore(
    noopSubscribe,
    () => typeof navigator !== "undefined" && typeof navigator.share === "function",
    () => false,
  );
  const fetchHourly = useCallback((pickId?: string | null, signal?: AbortSignal) => {
    fetch(pickId ? `${API_BASE}/pick/${encodeURIComponent(pickId)}` : `${API_BASE}/hourly`, { signal })
      .then(res => res.json())
      .then((data: HourlyResponse) => {
        setLoadFailed(false);
        setHourlyOne(prev => {
          // New hour, new item: reset the player and feedback state
          if (prev?.hourly?.id && data?.hourly?.id && prev.hourly.id !== data.hourly.id) {
            setIsPlaying(false);
          }
          return data;
        });
        setLoading(false);
      })
      .catch(err => {
        if (err?.name === "AbortError") return;  // superseded by a newer request
        console.error(err);
        setLoadFailed(true);
        setLoading(false);
      });
  }, []);

  // Stable, so the countdown's effect fires once when the slot turns over.
  const refreshLive = useCallback(() => fetchHourly(), [fetchHourly]);

  useEffect(() => {
    // The pick id is read from the URL after the first render, so this effect runs
    // once for "now" and again for the pinned pick. Without cancelling the first
    // request, whichever answer arrived last won -- a shared link could open on
    // the current pick instead of the one that was shared.
    const controller = new AbortController();
    fetchHourly(pinnedId, controller.signal);

    // Only the live view rolls over; a permalink must keep showing its own hour.
    const hourlyInterval = pinnedId ? null : setInterval(() => fetchHourly(), 60000);
    return () => {
      controller.abort();
      if (hourlyInterval) clearInterval(hourlyInterval);
    };
  }, [pinnedId, fetchHourly]);

  // One anonymous "view" per pick per visitor per day (deduplicated server-side).
  const viewedId = hourlyOne?.hourly?.id;
  useEffect(() => {
    if (viewedId) track(viewedId, "view");
  }, [viewedId]);

  const votes: Record<string, string> = (() => {
    try { return JSON.parse(votesJson || "{}"); } catch { return {}; }
  })();

  const handleFeedback = async (seenBefore: "NEVER_SEEN" | "KNEW_ALREADY") => {
    const hourlyId = hourlyOne?.hourly?.id;
    if (!hourlyId || votes[hourlyId] === seenBefore) return;

    // Remember the answer on this device, capped so the map cannot grow forever.
    // The server keeps one vote per visitor per pick, so changing it updates it.
    const next: Record<string, string> = { ...votes, [hourlyId]: seenBefore };
    const keys = Object.keys(next);
    for (const key of keys.slice(0, Math.max(0, keys.length - 200))) delete next[key];
    setVotesJson(JSON.stringify(next));

    try {
      await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hourly_one_id: hourlyId, seen_before: seenBefore })
      });
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen flex flex-col">
        <ApiWarning failed={loadFailed} />
        <div className="flex-1 flex items-center justify-center">
          <span className="label" style={{ color: 'var(--ink-faint)' }}>Loading ONE</span>
        </div>
      </main>
    );
  }

  const candidate: Candidate | null = hourlyOne?.candidate ?? null;
  const theme = (hourlyOne?.hourly?.theme || "Random").replace(/_/g, " ");
  const isStale = Boolean(hourlyOne?.is_stale);
  const myVote = hourlyOne?.hourly?.id ? votes[hourlyOne.hourly.id] : undefined;

  // Only offer playback when there is something to play. The previous build showed
  // a Play badge even on the empty state, so clicking it did nothing at all.
  // Ids are checked before they reach a player URL: they come from third-party feeds.
  const sourceId = candidate?.source_id || "";
  const youtubeId = candidate?.source_type === "YOUTUBE" && /^[\w-]{6,20}$/.test(sourceId) ? sourceId : null;
  const vimeoId = candidate?.source_type === "VIMEO" && /^\d{1,15}$/.test(sourceId) ? sourceId : null;
  const audioUrl = candidate?.source_type === "PODCAST" ? safeExternalUrl(sourceId) : undefined;
  const canEmbed = Boolean(youtubeId || vimeoId || audioUrl);
  const playable = Boolean(canEmbed || safeExternalUrl(candidate?.url));
  const sourceLabel = candidate ? SOURCE_LABELS[candidate.source_type] || candidate.source_type : "";

  // The affordance says what will happen: a player for films, audio for podcasts,
  // a new tab for everything else.
  const actionLabel = audioUrl ? "Listen" : canEmbed ? "Play" : "Read";

  const sourceUrl = safeExternalUrl(candidate?.url);
  const creatorUrl = safeExternalUrl(candidate?.creator_url);

  const handlePlay = () => {
    const id = hourlyOne?.hourly?.id;
    if (canEmbed) {
      track(id, "play");
      setIsPlaying(true);
    } else if (sourceUrl) {
      track(id, "read");
      window.open(sourceUrl, "_blank", "noopener,noreferrer");
    }
  };

  const handleShare = async () => {
    const id = hourlyOne?.hourly?.id;
    if (!id) return;
    track(id, "copy_link");
    try {
      await navigator.clipboard.writeText(permalinkFor(id));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be blocked; the address bar still works as a fallback.
    }
  };

  const shareText = candidate ? `${candidate.title} — via ONE` : "ONE";

  const openShare = (kind: "share_x" | "share_bluesky") => {
    const id = hourlyOne?.hourly?.id;
    if (!id) return;
    track(id, kind);
    const url = permalinkFor(id);
    const target = kind === "share_x" ? xShareUrl(shareText, url) : blueskyShareUrl(shareText, url);
    window.open(target, "_blank", "noopener,noreferrer");
  };

  const nativeShare = async () => {
    const id = hourlyOne?.hourly?.id;
    if (!id) return;
    try {
      await navigator.share({ title: candidate?.title || "ONE", text: shareText, url: permalinkFor(id) });
      track(id, "share_native");
    } catch {
      // Dismissing the share sheet rejects the promise; that is not an error.
    }
  };

  return (
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
      <ApiWarning failed={loadFailed} />

      {/* Ribbon */}
      <header
        className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
        style={{ borderBottom: '2px solid var(--rule)' }}
      >
        <div className="flex flex-col">
          <span className="display text-2xl font-bold tracking-tight leading-none">ONE</span>
          <span className="label mt-1" style={{ color: 'var(--accent)' }}>{theme}</span>
        </div>
        <div className="flex items-center gap-5">
          {hourlyOne?.next_publish_time && (
            <span className="label" style={{ color: 'var(--ink-faint)' }}>
              <span className="hidden sm:inline">Next pick in </span>
              <Countdown
                target={hourlyOne.next_publish_time}
                onElapsed={pinnedId ? undefined : refreshLive}
              />
            </span>
          )}
          <Link href="/archive" className="label link-accent">Archive</Link>
        </div>
      </header>

      {pinnedId && (
        <div
          className="w-full px-6 md:px-10 py-3 flex flex-wrap items-center justify-between gap-3"
          style={{ background: 'var(--accent-wash)', borderBottom: '1px solid var(--line)' }}
        >
          <p className="label" style={{ color: 'var(--accent)' }}>
            From the archive{hourlyOne?.hourly?.publish_time
              ? ` / ${new Date(hourlyOne.hourly.publish_time + "Z").toLocaleString('en-US',
                  { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric' })}`
              : ""}
          </p>
          <Link href="/" className="label link-accent">Go to the current pick &#8594;</Link>
        </div>
      )}

      <div className="mx-auto px-6 md:px-10 py-10 md:py-16" style={{ maxWidth: 'var(--content-max)' }}>

        <p className="label" style={{ color: 'var(--ink-faint)' }}>
          {pinnedId ? "A Past Diamond" : isStale ? "The Latest Pick" : "Current Feature"}
        </p>

        <h1 className="display mt-3 text-3xl md:text-5xl font-normal leading-tight">
          {candidate ? candidate.title : "We are discovering something amazing…"}
        </h1>

        <p className="mt-3 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
          {candidate ? (
            <>
              {creatorUrl ? (
                <a href={creatorUrl} target="_blank" rel="noopener noreferrer" className="link-accent">
                  {candidate.creator_name}
                </a>
              ) : candidate.creator_name}
              <span style={{ color: 'var(--line-strong)' }}> / </span>
              {sourceLabel}
            </>
          ) : "The engine is selecting the next diamond."}
        </p>

        {candidate?.preview_text && (
          <p className="mt-5 text-[17px] leading-relaxed" style={{ color: 'var(--ink)' }}>
            {candidate.preview_text}
          </p>
        )}

        {/* Media */}
        <div className="mt-8">
          {isPlaying && audioUrl ? (
            // Rendered only once Listen is pressed, so nothing is requested from the
            // podcast's audio host before then.
            <div style={{ border: '1px solid var(--line-strong)' }}>
              <Thumbnail
                src={candidate?.thumbnail_url}
                alt={candidate?.title || ""}
                className="w-full aspect-video"
                fallback={null}
              />
              <audio className="w-full block" src={audioUrl} controls autoPlay preload="none" />
            </div>
          ) : isPlaying && canEmbed ? (
            <div className="w-full aspect-video" style={{ border: '1px solid var(--line-strong)' }}>
              <iframe
                className="w-full h-full"
                src={youtubeId
                  ? `https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&rel=0`
                  : `https://player.vimeo.com/video/${vimeoId}?dnt=1&autoplay=1`}
                title={candidate!.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; fullscreen; gyroscope; picture-in-picture; web-share"
                referrerPolicy="strict-origin-when-cross-origin"
                allowFullScreen
              />
            </div>
          ) : (
            <div
              onClick={playable ? handlePlay : undefined}
              role={playable ? "button" : undefined}
              tabIndex={playable ? 0 : undefined}
              onKeyDown={playable ? (e) => { if (e.key === 'Enter' || e.key === ' ') handlePlay(); } : undefined}
              aria-label={playable && candidate ? `${actionLabel}: ${candidate.title}` : undefined}
              className="w-full aspect-video relative overflow-hidden"
              style={{
                border: '1px solid var(--line-strong)',
                background: 'var(--sunken)',
                cursor: playable ? 'pointer' : 'default',
              }}
            >
              <Thumbnail
                src={candidate?.thumbnail_url}
                alt={candidate?.title || ""}
                className="absolute inset-0 w-full h-full"
                fallback={
                  // No image: show the opening of the piece rather than a blank
                  // rectangle, so the gist is readable at a glance.
                  <div className="h-full flex flex-col justify-center px-6 md:px-10 py-6">
                    <p className="label" style={{ color: 'var(--accent)' }}>
                      {candidate?.tone || sourceLabel || "Reading"}
                    </p>
                    <p className="display mt-2 text-lg md:text-2xl leading-snug"
                       style={{ color: 'var(--ink)' }}>
                      {candidate?.preview_text
                        ? candidate.preview_text.slice(0, 220)
                        : candidate?.title}
                    </p>
                  </div>
                }
              />

              {playable ? (
                <div
                  className="absolute inset-0 flex items-center justify-center"
                  style={{ background: 'rgba(26,16,10,0.30)' }}
                >
                  <span
                    className="label flex items-center gap-2 px-5 py-3"
                    style={{
                      background: 'var(--accent)',
                      color: 'var(--ink-inverse)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    {audioUrl ? <Headphones size={14} />
                      : canEmbed ? <Play size={14} fill="currentColor" /> : <BookOpen size={14} />}
                    {actionLabel}
                  </span>
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="label" style={{ color: 'var(--ink-faint)' }}>Nothing scheduled yet</span>
                </div>
              )}
            </div>
          )}

          {/* Escape hatch: some videos disallow embedding and browsers can block
              autoplay, so a direct link keeps playback from being a dead end. */}
          <div className="mt-2 flex items-center justify-between gap-4">
            {hourlyOne?.hourly?.id ? (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <button
                  onClick={handleShare}
                  className="label flex items-center gap-2 link-accent"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  {copied ? <Check size={14} /> : <Link2 size={14} />}
                  {copied ? "Link copied" : "Copy link"}
                </button>
                <button
                  onClick={() => openShare("share_x")}
                  className="label link-accent"
                  aria-label="Share on X"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  X
                </button>
                <button
                  onClick={() => openShare("share_bluesky")}
                  className="label link-accent"
                  aria-label="Share on Bluesky"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  Bluesky
                </button>
                {canNativeShare && (
                  <button
                    onClick={nativeShare}
                    className="label link-accent"
                    style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    Share&hellip;
                  </button>
                )}
              </div>
            ) : <span />}
            {sourceUrl && (
              <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="label link-accent"
                 onClick={() => track(hourlyOne?.hourly?.id, "open_original")}>
                {canEmbed ? "Watch on YouTube" : "Open the original"} &#8599;
              </a>
            )}
          </div>
        </div>

        {/* Editorial note */}
        {candidate?.ai_explanation && (
          <>
            <div className="mt-10" style={{ height: 1, background: 'var(--line)' }} />
            <p className="label mt-6" style={{ color: 'var(--ink-faint)' }}>Why this one</p>
            <p className="display mt-3 text-lg md:text-xl leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
              {candidate.ai_explanation}
            </p>
          </>
        )}

        {/* Feedback */}
        <div className="mt-12" style={{ height: 1, background: 'var(--line)' }} />
        <div className="mt-8">
          <p className="label" style={{ color: 'var(--ink-faint)' }}>Was this new to you?</p>
          <div className="flex flex-col sm:flex-row gap-3 mt-4" role="group" aria-label="Was this new to you?">
            <button
              onClick={() => handleFeedback("NEVER_SEEN")}
              disabled={!hourlyOne?.hourly?.id}
              aria-pressed={myVote === "NEVER_SEEN"}
              className={`btn flex-1 ${myVote === "KNEW_ALREADY" ? "btn-secondary" : "btn-primary"}`}
            >
              {myVote === "NEVER_SEEN" && <span aria-hidden="true">&#10003; </span>}New to me
            </button>
            <button
              onClick={() => handleFeedback("KNEW_ALREADY")}
              disabled={!hourlyOne?.hourly?.id}
              aria-pressed={myVote === "KNEW_ALREADY"}
              className={`btn flex-1 ${myVote === "KNEW_ALREADY" ? "btn-primary" : "btn-secondary"}`}
            >
              {myVote === "KNEW_ALREADY" && <span aria-hidden="true">&#10003; </span>}Already knew this
            </button>
          </div>
          {myVote && (
            <p className="text-[15px] mt-3" style={{ color: 'var(--ink-muted)' }}>
              Thank you &mdash; your answer shapes what we surface next. Changed your mind? Choose the other one.
            </p>
          )}
        </div>
      </div>

    </main>
  );
}
