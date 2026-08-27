"use client";

import { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QueueCandidate {
  id: string;
  title: string;
  creator_name: string;
  url: string;
  source_type: string;
  theme: string | null;
  view_count: number | null;
  subscriber_count: number | null;
  diamond_score: number | null;
  quality_score: number | null;
  interestingness_score: number | null;
  rarity_score: number | null;
  originality_score: number | null;
  outlier_score: number | null;
  clickbait_penalty: number | null;
  trustworthiness_score: number | null;
  ai_explanation: string | null;
}

function num(value: number | null): string {
  return value == null ? "–" : String(Math.round(value));
}

export default function Admin() {
  const [token, setToken] = useState("");
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [status, setStatus] = useState("Enter the admin token to load the queue.");
  const [busy, setBusy] = useState(false);

  const loadQueue = useCallback(async (adminToken: string) => {
    if (!adminToken) return;
    setStatus("Loading queue...");
    try {
      const res = await fetch(`${API_BASE}/admin/queue?limit=15`, {
        headers: { "X-Admin-Token": adminToken }
      });
      if (res.status === 403) {
        setStatus("Invalid admin token.");
        setQueue([]);
        return;
      }
      const data = await res.json();
      setQueue(Array.isArray(data) ? data : []);
      setStatus(`${Array.isArray(data) ? data.length : 0} candidates pending review, ranked by Diamond Score.`);
    } catch (err) {
      console.error(err);
      setStatus("Could not reach the API.");
    }
  }, []);

  useEffect(() => {
    let stored = "";
    try {
      stored = localStorage.getItem("one_admin_token") || "";
    } catch { /* storage unavailable */ }
    setToken(stored);
    if (stored) loadQueue(stored);
  }, [loadQueue]);

  const handleTokenSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      localStorage.setItem("one_admin_token", token);
    } catch { /* storage unavailable */ }
    loadQueue(token);
  };

  const act = async (path: "schedule" | "reject", candidateId: string) => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/admin/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify({ candidate_id: candidateId })
      });
      const data = await res.json();
      if (res.ok) {
        setStatus(path === "schedule"
          ? "Featured for the current hour. The displaced pick (if any) is back in the queue."
          : "Candidate rejected.");
        await loadQueue(token);
      } else {
        setStatus(`Error: ${data.detail || res.status}`);
      }
    } catch (err) {
      console.error(err);
      setStatus("Request failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#FDFDFD] text-[#111111] font-sans p-6 md:p-16">
      <header className="max-w-5xl mx-auto mb-8">
        <a href="/" className="text-xl font-bold tracking-tighter hover:text-gray-500 transition-colors">ONE</a>
        <h1 className="text-3xl font-medium tracking-tight mt-2">Review Queue</h1>
        <p className="text-sm text-gray-500 mt-1">{status}</p>
        <form onSubmit={handleTokenSubmit} className="mt-4 flex gap-2 max-w-md">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Admin token"
            className="flex-1 bg-gray-100 border-none rounded px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-black"
          />
          <button type="submit" className="bg-black text-white px-4 py-2 text-sm font-bold uppercase tracking-wider hover:bg-gray-800 transition-colors">
            Load
          </button>
        </form>
      </header>

      <div className="max-w-5xl mx-auto flex flex-col gap-6">
        {queue.map((c, rank) => (
          <div key={c.id} className="border border-gray-200 bg-white p-5">
            <div className="flex flex-wrap justify-between items-start gap-4">
              <div className="min-w-0">
                <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                  #{rank + 1} &middot; {c.source_type} &middot; {(c.theme || "?").replace(/_/g, " ")}
                </div>
                <a href={c.url} target="_blank" rel="noopener noreferrer"
                   className="text-lg font-medium leading-snug hover:text-gray-500 transition-colors">
                  {c.title}
                </a>
                <div className="text-sm text-gray-500">{c.creator_name}
                  {c.view_count != null && <> &middot; {c.view_count.toLocaleString()} views</>}
                  {c.subscriber_count != null && c.subscriber_count > 0 && <> / {c.subscriber_count.toLocaleString()} subs</>}
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => act("schedule", c.id)}
                  disabled={busy}
                  className="bg-black text-white px-4 py-2 text-xs font-bold uppercase tracking-wider hover:bg-gray-800 transition-colors disabled:opacity-40"
                >
                  Feature Now
                </button>
                <button
                  onClick={() => act("reject", c.id)}
                  disabled={busy}
                  className="bg-white border-2 border-black px-4 py-2 text-xs font-bold uppercase tracking-wider hover:bg-gray-50 transition-colors disabled:opacity-40"
                >
                  Reject
                </button>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-600 font-mono">
              <span className="font-bold">Diamond {num(c.diamond_score)}</span>
              <span>Quality {num(c.quality_score)}</span>
              <span>Interest {num(c.interestingness_score)}</span>
              <span>Rarity {num(c.rarity_score)}</span>
              <span>Original {num(c.originality_score)}</span>
              <span>Outlier +{num(c.outlier_score)}</span>
              <span>Clickbait {num(c.clickbait_penalty)}</span>
              <span>Trust {num(c.trustworthiness_score)}</span>
            </div>
            {c.ai_explanation && (
              <p className="mt-2 text-sm text-gray-600 font-serif italic">{c.ai_explanation}</p>
            )}
          </div>
        ))}
      </div>
    </main>
  );
}
