"use client";

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { MessageSquare, X, Send, Play, BookOpen, Link2, Check } from 'lucide-react';
import { API_BASE } from '@/lib/api';
import ApiWarning from '@/components/api-warning';
import Thumbnail from '@/components/thumbnail';
import Countdown from '@/components/countdown';
import { usePersistentState } from '@/lib/use-persistent-state';
import { safeExternalUrl, permalinkFor } from '@/lib/url';
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

interface HourlyResponse {
  hourly?: { id: string; theme: string; publish_time?: string };
  candidate?: Candidate;
  is_stale?: boolean;
  is_permalink?: boolean;
  next_publish_time?: string;
}

interface Comment {
  id: string;
  content: string;
  display_name?: string | null;
}

export default function Home() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [newComment, setNewComment] = useState("");
  const [displayName, setDisplayName] = usePersistentState("one_display_name");

  const [hourlyOne, setHourlyOne] = useState<HourlyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  // Answers remembered on this device only, so the chosen one shows and can be changed.
  const [votesJson, setVotesJson] = usePersistentState("one_votes");
  const [copied, setCopied] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  // A ?pick=<id> URL pins the page to one archived hour instead of "now".
  const pinnedId = usePickParam();
  const chatPanelRef = useRef<HTMLDivElement>(null);
  const chatToggleRef = useRef<HTMLButtonElement>(null);

  const fetchHourly = useCallback((pickId?: string | null) => {
    fetch(pickId ? `${API_BASE}/pick/${encodeURIComponent(pickId)}` : `${API_BASE}/hourly`)
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
        console.error(err);
        setLoadFailed(true);
        setLoading(false);
      });
  }, []);

  const fetchComments = useCallback(() => {
    fetch(`${API_BASE}/comments`)
      .then(res => res.json())
      .then(data => setComments(Array.isArray(data) ? data : []))
      .catch(err => console.error(err));
  }, []);

  // Stable, so the countdown's effect fires once when the slot turns over.
  const refreshLive = useCallback(() => fetchHourly(), [fetchHourly]);

  useEffect(() => {
    fetchHourly(pinnedId);
    fetchComments();

    const commentInterval = setInterval(fetchComments, 10000);
    // Only the live view rolls over; a permalink must keep showing its own hour.
    const hourlyInterval = pinnedId ? null : setInterval(() => fetchHourly(), 60000);
    return () => {
      clearInterval(commentInterval);
      if (hourlyInterval) clearInterval(hourlyInterval);
    };
  }, [pinnedId, fetchHourly, fetchComments]);

  // Escape closes the chat, and focus moves into and back out of the panel.
  useEffect(() => {
    if (!isChatOpen) return;
    chatPanelRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsChatOpen(false);
        chatToggleRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isChatOpen]);

  // One anonymous "view" per pick per visitor per day (deduplicated server-side).
  const viewedId = hourlyOne?.hourly?.id;
  useEffect(() => {
    if (viewedId) track(viewedId, "view");
  }, [viewedId]);

  const handleSendComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    const commentText = newComment;
    setNewComment("");

    try {
      const res = await fetch(`${API_BASE}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: commentText, display_name: displayName.trim() || null })
      });
      if (res.ok) fetchComments();
    } catch (err) {
      console.error(err);
    }
  };

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
  const canEmbed = Boolean(candidate?.source_type === "YOUTUBE" && candidate?.source_id);
  const playable = Boolean(canEmbed || safeExternalUrl(candidate?.url));

  // Most picks are now articles rather than videos, so the affordance has to say
  // which it is: an embedded player for YouTube, a new tab for everything else.
  const actionLabel = canEmbed ? "Play" : "Read";

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
          <button
            ref={chatToggleRef}
            onClick={() => setIsChatOpen(true)}
            aria-expanded={isChatOpen}
            className="label flex items-center gap-2 link-accent"
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <MessageSquare size={16} />
            <span>Chat ({comments.length})</span>
          </button>
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
              {candidate.source_type}
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
          {isPlaying && canEmbed ? (
            <div className="w-full aspect-video" style={{ border: '1px solid var(--line-strong)' }}>
              <iframe
                className="w-full h-full"
                src={`https://www.youtube-nocookie.com/embed/${candidate!.source_id}?autoplay=1&rel=0`}
                title={candidate!.title}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
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
                      {candidate?.tone || candidate?.source_type || "Reading"}
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
                    {canEmbed ? <Play size={14} fill="currentColor" /> : <BookOpen size={14} />}
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
              <button
                onClick={handleShare}
                className="label flex items-center gap-2 link-accent"
                style={{ background: 'none', border: 'none', cursor: 'pointer' }}
              >
                {copied ? <Check size={14} /> : <Link2 size={14} />}
                {copied ? "Link copied" : "Copy link"}
              </button>
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

      {/* Chat panel */}
      <div
        ref={chatPanelRef}
        // Off-screen is not hidden: without inert the panel stays focusable and
        // announced, so keyboard and screen-reader users land inside an invisible
        // dialog. inert removes it from the tab order and the a11y tree entirely.
        inert={!isChatOpen}
        aria-hidden={!isChatOpen}
        role="dialog"
        aria-label="Daily Lobby chat"
        tabIndex={-1}
        className={`fixed top-0 right-0 h-full w-full md:w-[380px] z-50 flex flex-col transition-transform duration-200 ease-in-out ${
          isChatOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ background: 'var(--surface)', borderLeft: '1px solid var(--line-strong)', outline: 'none' }}
      >
        <div className="px-5 py-4 flex justify-between items-center" style={{ borderBottom: '2px solid var(--rule)' }}>
          <div>
            <p className="display text-lg leading-none">Daily Lobby</p>
            <p className="label mt-1" style={{ color: 'var(--ink-faint)' }}>Clears at midnight</p>
          </div>
          <button
            onClick={() => { setIsChatOpen(false); chatToggleRef.current?.focus(); }}
            aria-label="Close chat"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-muted)' }}
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {comments.length === 0 ? (
            <p className="text-sm mt-4" style={{ color: 'var(--ink-faint)' }}>
              No one has said anything yet today.
            </p>
          ) : (
            comments.map((c, i) => (
              <div key={c.id ?? i} className="pb-3" style={{ borderBottom: '1px solid var(--line)' }}>
                <p className="label" style={{ color: 'var(--accent)' }}>{c.display_name || "Anonymous"}</p>
                <p className="text-[15px] mt-1" style={{ color: 'var(--ink)' }}>{c.content}</p>
              </div>
            ))
          )}
        </div>

        <div className="px-5 py-4 flex flex-col gap-2" style={{ borderTop: '1px solid var(--line)' }}>
          <input
            type="text"
            value={displayName}
            maxLength={40}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your name (optional)"
            className="w-full px-3 py-2 text-sm outline-none"
            style={{
              background: 'var(--paper)', color: 'var(--ink)',
              border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)',
            }}
          />
          <form onSubmit={handleSendComment} className="flex gap-2">
            <input
              type="text"
              value={newComment}
              maxLength={500}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Say something..."
              className="flex-1 px-3 py-2 text-sm outline-none"
              style={{
                background: 'var(--paper)', color: 'var(--ink)',
                border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm)',
              }}
            />
            <button
              type="submit"
              aria-label="Send message"
              className="flex items-center justify-center"
              style={{
                background: 'var(--accent)', color: 'var(--ink-inverse)',
                border: 'none', borderRadius: 'var(--radius-sm)',
                width: 44, minHeight: 40, cursor: 'pointer',
              }}
            >
              <Send size={15} />
            </button>
          </form>
        </div>
      </div>

      {isChatOpen && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          style={{ background: 'rgba(26,16,10,0.35)' }}
          onClick={() => setIsChatOpen(false)}
        />
      )}
    </main>
  );
}
