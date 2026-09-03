"use client";

import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, X, Send, Play } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
}

interface HourlyResponse {
  hourly?: { id: string; theme: string };
  candidate?: Candidate;
  is_stale?: boolean;
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
  const [displayName, setDisplayName] = useState("");

  const [hourlyOne, setHourlyOne] = useState<HourlyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState(false);

  const fetchHourly = useCallback(() => {
    fetch(`${API_BASE}/hourly`)
      .then(res => res.json())
      .then((data: HourlyResponse) => {
        setHourlyOne(prev => {
          // New hour, new item: reset the player and feedback state
          if (prev?.hourly?.id && data?.hourly?.id && prev.hourly.id !== data.hourly.id) {
            setIsPlaying(false);
            setFeedbackGiven(false);
          }
          return data;
        });
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const fetchComments = useCallback(() => {
    fetch(`${API_BASE}/comments`)
      .then(res => res.json())
      .then(data => setComments(Array.isArray(data) ? data : []))
      .catch(err => console.error(err));
  }, []);

  useEffect(() => {
    try {
      setDisplayName(localStorage.getItem("one_display_name") || "");
    } catch { /* storage unavailable (private mode etc.) - stay anonymous */ }

    fetchHourly();
    fetchComments();

    // Poll comments every 10s, and re-check the hourly item every 60s so an
    // open tab rolls over when a new hour is scheduled.
    const commentInterval = setInterval(fetchComments, 10000);
    const hourlyInterval = setInterval(fetchHourly, 60000);
    return () => {
      clearInterval(commentInterval);
      clearInterval(hourlyInterval);
    };
  }, [fetchHourly, fetchComments]);

  const handleNameChange = (name: string) => {
    setDisplayName(name);
    try {
      localStorage.setItem("one_display_name", name);
    } catch { /* storage unavailable - the name simply will not persist */ }
  };

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

  const handleFeedback = async (seenBefore: "NEVER_SEEN" | "KNEW_ALREADY") => {
    const hourlyId = hourlyOne?.hourly?.id;
    if (!hourlyId || feedbackGiven) return;

    setFeedbackGiven(true);
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
      <main className="min-h-screen flex items-center justify-center">
        <span className="label" style={{ color: 'var(--ink-faint)' }}>Loading ONE</span>
      </main>
    );
  }

  const candidate: Candidate | null = hourlyOne?.candidate ?? null;
  const theme = (hourlyOne?.hourly?.theme || "Random").replace(/_/g, " ");
  const isStale = Boolean(hourlyOne?.is_stale);

  // Only offer playback when there is something to play. The previous build showed
  // a Play badge even on the empty state, so clicking it did nothing at all.
  const canEmbed = Boolean(candidate?.source_type === "YOUTUBE" && candidate?.source_id);
  const playable = Boolean(canEmbed || candidate?.url);

  const handlePlay = () => {
    if (canEmbed) setIsPlaying(true);
    else if (candidate?.url) window.open(candidate.url, "_blank", "noopener,noreferrer");
  };

  return (
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>

      {/* Ribbon */}
      <header
        className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
        style={{ borderBottom: '2px solid var(--rule)' }}
      >
        <div className="flex flex-col">
          <span className="display text-2xl font-bold tracking-tight leading-none">ONE</span>
          <span className="label mt-1" style={{ color: 'var(--accent)' }}>{theme} Hour</span>
        </div>
        <div className="flex items-center gap-5">
          <span className="label hidden sm:block" style={{ color: 'var(--ink-faint)' }}>
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </span>
          <a href="/archive/" className="label link-accent">Archive</a>
          <button
            onClick={() => setIsChatOpen(true)}
            className="label flex items-center gap-2 link-accent"
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
          >
            <MessageSquare size={16} />
            <span>Chat ({comments.length})</span>
          </button>
        </div>
      </header>

      <div className="mx-auto px-6 md:px-10 py-10 md:py-16" style={{ maxWidth: 'var(--content-max)' }}>

        <p className="label" style={{ color: 'var(--ink-faint)' }}>
          {isStale ? "Most Recent Pick" : "Current Feature"}
        </p>

        <h1 className="display mt-3 text-3xl md:text-5xl font-normal leading-tight">
          {candidate ? candidate.title : "We are discovering something amazing…"}
        </h1>

        <p className="mt-3 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
          {candidate ? (
            <>
              {candidate.creator_url ? (
                <a href={candidate.creator_url} target="_blank" rel="noopener noreferrer" className="link-accent">
                  {candidate.creator_name}
                </a>
              ) : candidate.creator_name}
              <span style={{ color: 'var(--line-strong)' }}> / </span>
              {candidate.source_type}
            </>
          ) : "The engine is selecting the next diamond."}
        </p>

        {/* Media */}
        <div className="mt-8">
          {isPlaying && canEmbed ? (
            <div className="w-full aspect-video" style={{ border: '1px solid var(--line-strong)' }}>
              <iframe
                className="w-full h-full"
                src={`https://www.youtube.com/embed/${candidate!.source_id}?autoplay=1`}
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
              aria-label={playable && candidate ? `Play ${candidate.title}` : undefined}
              className="w-full aspect-video relative overflow-hidden"
              style={{
                border: '1px solid var(--line-strong)',
                background: candidate?.thumbnail_url
                  ? `url(${candidate.thumbnail_url}) center/cover`
                  : 'var(--sunken)',
                cursor: playable ? 'pointer' : 'default',
              }}
            >
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
                    <Play size={14} fill="currentColor" /> Play
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
          {candidate?.url && (
            <p className="mt-2 text-right">
              <a href={candidate.url} target="_blank" rel="noopener noreferrer" className="label link-accent">
                Watch on {candidate.source_type === "YOUTUBE" ? "YouTube" : "the source"} &#8599;
              </a>
            </p>
          )}
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
          {feedbackGiven ? (
            <p className="text-[15px]" style={{ color: 'var(--ink-muted)' }}>
              Thank you &mdash; your answer decides what we surface next.
            </p>
          ) : (
            <>
              <p className="label" style={{ color: 'var(--ink-faint)' }}>Had you seen this before?</p>
              <div className="flex flex-col sm:flex-row gap-3 mt-4">
                <button
                  onClick={() => handleFeedback("NEVER_SEEN")}
                  disabled={!hourlyOne?.hourly?.id}
                  className="btn btn-primary flex-1"
                >
                  Never Seen It
                </button>
                <button
                  onClick={() => handleFeedback("KNEW_ALREADY")}
                  disabled={!hourlyOne?.hourly?.id}
                  className="btn btn-secondary flex-1"
                >
                  I Knew This
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Chat panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full md:w-[380px] z-50 flex flex-col transition-transform duration-200 ease-in-out ${
          isChatOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ background: 'var(--surface)', borderLeft: '1px solid var(--line-strong)' }}
      >
        <div className="px-5 py-4 flex justify-between items-center" style={{ borderBottom: '2px solid var(--rule)' }}>
          <div>
            <p className="display text-lg leading-none">Daily Lobby</p>
            <p className="label mt-1" style={{ color: 'var(--ink-faint)' }}>Clears at midnight</p>
          </div>
          <button
            onClick={() => setIsChatOpen(false)}
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
            onChange={(e) => handleNameChange(e.target.value)}
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
