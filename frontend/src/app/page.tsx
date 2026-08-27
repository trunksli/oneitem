"use client";

import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, X, Send } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Candidate {
  id?: string;
  url?: string;
  source_id?: string;
  source_type: string;
  title: string;
  creator_name: string;
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

    // Poll for new comments every 10s, and re-check the hourly item every 60s
    // so an open tab rolls over when a new hour is scheduled.
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
    } catch { /* storage unavailable - name just won't persist */ }
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
      if (res.ok) {
        fetchComments();
      }
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

  const handlePlay = () => {
    if (!candidate) return;
    if (candidate.source_type === "YOUTUBE" && candidate.source_id) {
      setIsPlaying(true);
    } else if (candidate.url) {
      window.open(candidate.url, "_blank", "noopener,noreferrer");
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading ONE...</div>;
  }

  // Fallback if DB is empty
  const candidate: Candidate = hourlyOne?.candidate || {
    title: "We are discovering something amazing...",
    creator_name: "ONE Engine",
    source_type: "System",
    ai_explanation: "Check back shortly when the AI selects the next diamond.",
    thumbnail_url: ""
  };
  const theme = (hourlyOne?.hourly?.theme || "Random").replace(/_/g, " ");

  return (
    <main className="min-h-screen bg-[#FDFDFD] text-[#111111] font-sans flex flex-col items-center justify-center p-6 md:p-24 selection:bg-black selection:text-white relative overflow-hidden">

      {/* Header */}
      <header className="absolute top-0 w-full p-8 flex justify-between items-center z-10">
        <div className="flex flex-col">
           <h1 className="text-xl font-bold tracking-tighter">ONE</h1>
           <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">{theme} Hour</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-sm font-medium tracking-wide text-gray-500 uppercase hidden sm:block">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </div>
          <a
            href="/archive/"
            className="text-sm font-bold tracking-widest uppercase hover:text-gray-500 transition-colors"
          >
            Archive
          </a>
          <button
            onClick={() => setIsChatOpen(true)}
            className="flex items-center gap-2 text-sm font-bold tracking-widest uppercase hover:text-gray-500 transition-colors"
          >
            <MessageSquare size={18} />
            <span>Chat ({comments.length})</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className={`max-w-4xl w-full flex flex-col items-center gap-12 mt-16 transition-all duration-500 ${isChatOpen ? 'md:-translate-x-48 opacity-50 md:opacity-100' : ''}`}>

        <div className="text-center space-y-4">
          <p className="text-sm tracking-widest uppercase text-gray-400">Current Feature</p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-medium tracking-tight leading-tight max-w-3xl">
            {candidate.title}
          </h2>
          <div className="flex items-center justify-center gap-2 text-gray-500 font-medium">
            <span>{candidate.creator_name}</span>
            <span>&middot;</span>
            <span>{candidate.source_type}</span>
          </div>
        </div>

        {/* Media */}
        {isPlaying && candidate.source_id ? (
          <div className="w-full aspect-video border border-gray-200">
            <iframe
              className="w-full h-full"
              src={`https://www.youtube.com/embed/${candidate.source_id}?autoplay=1`}
              title={candidate.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          </div>
        ) : (
          <div
            className="w-full aspect-video bg-gray-100 relative overflow-hidden group cursor-pointer border border-gray-200"
            onClick={handlePlay}
            style={candidate.thumbnail_url ? { backgroundImage: `url(${candidate.thumbnail_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}
          >
            <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-transparent transition-colors">
              <span className="text-white font-medium tracking-widest uppercase group-hover:scale-105 transition-transform duration-500 bg-black/50 px-4 py-2 rounded">
                Play
              </span>
            </div>
          </div>
        )}

        {/* Editorial Explanation */}
        <div className="max-w-2xl text-center">
          <p className="text-lg md:text-xl text-gray-600 leading-relaxed font-serif italic">
            "{candidate.ai_explanation}"
          </p>
        </div>

        {/* Feedback Section */}
        <div className="mt-16 pt-16 border-t border-gray-200 w-full flex flex-col items-center gap-8">
          {feedbackGiven ? (
            <h3 className="text-lg font-medium text-gray-500">Thanks — your feedback helps pick the next ONE.</h3>
          ) : (
            <>
              <h3 className="text-lg font-medium">Have you seen this before?</h3>
              <div className="flex gap-4 w-full max-w-md">
                <button
                  onClick={() => handleFeedback("NEVER_SEEN")}
                  disabled={!hourlyOne?.hourly?.id}
                  className="flex-1 py-4 px-6 bg-black text-white text-sm font-bold tracking-wider uppercase hover:bg-gray-800 transition-colors disabled:opacity-40"
                >
                  Never Seen It
                </button>
                <button
                  onClick={() => handleFeedback("KNEW_ALREADY")}
                  disabled={!hourlyOne?.hourly?.id}
                  className="flex-1 py-4 px-6 bg-white border-2 border-black text-black text-sm font-bold tracking-wider uppercase hover:bg-gray-50 transition-colors disabled:opacity-40"
                >
                  I Knew This
                </button>
              </div>
            </>
          )}
        </div>

      </div>

      {/* Sliding Chat Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full md:w-96 bg-white border-l border-gray-200 shadow-2xl transform transition-transform duration-500 ease-in-out z-50 flex flex-col ${
          isChatOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50">
          <div>
             <h3 className="font-bold tracking-wider uppercase text-sm">Daily Lobby</h3>
             <p className="text-xs text-gray-500">Clears at midnight</p>
          </div>
          <button
            onClick={() => setIsChatOpen(false)}
            className="text-gray-500 hover:text-black transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
          {comments.length === 0 ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm italic">
              Be the first to comment today.
            </div>
          ) : (
            comments.map((c, i) => (
              <div key={c.id ?? i} className="bg-gray-100 p-4 rounded-lg text-sm text-gray-800">
                <div className="font-bold text-xs text-gray-500 mb-1">{c.display_name || "Anonymous"}</div>
                {c.content}
              </div>
            ))
          )}
        </div>

        <div className="p-4 border-t border-gray-200 bg-white space-y-2">
          <input
            type="text"
            value={displayName}
            maxLength={40}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Your name (optional)"
            className="w-full bg-gray-50 border border-gray-200 rounded-full px-4 py-1.5 text-xs outline-none focus:ring-2 focus:ring-black"
          />
          <form onSubmit={handleSendComment} className="flex gap-2">
            <input
              type="text"
              value={newComment}
              maxLength={500}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Join the conversation..."
              className="flex-1 bg-gray-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-black"
            />
            <button
              type="submit"
              className="bg-black text-white p-2 rounded-full hover:bg-gray-800 transition-colors flex items-center justify-center w-10 h-10"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>

      {/* Overlay for mobile to close chat */}
      {isChatOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-20 z-40 md:hidden"
          onClick={() => setIsChatOpen(false)}
        />
      )}

    </main>
  );
}
