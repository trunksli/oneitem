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

interface SourceStats {
  creator_name: string;
  source_type: string;
  candidates: number;
  avg_diamond: number | null;
  rejected: number;
  picks_featured: number;
  never_seen: number;
  knew_already: number;
  never_seen_rate: number | null;
  avg_growth_ratio: number | null;
  outcomes_checked: number;
  blowups: number;
}

interface Outcome {
  hourly_id: string;
  publish_time: string;
  title: string | null;
  creator_name: string | null;
  views_at_feature: number | null;
  views_after_7d: number | null;
  growth_ratio: number | null;
  never_seen: number;
  knew_already: number;
  diamond_score: number | null;
  quality_score: number | null;
  interestingness_score: number | null;
  rarity_score: number | null;
  originality_score: number | null;
  outlier_score: number | null;
  clickbait_penalty: number | null;
}

function num(value: number | null): string {
  return value == null ? "–" : String(Math.round(value));
}

function compact(value: number | null): string {
  if (value == null) return "–";
  return Intl.NumberFormat('en-US', { notation: 'compact' }).format(value);
}

export default function Admin() {
  const [token, setToken] = useState("");
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [sources, setSources] = useState<SourceStats[]>([]);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
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

      const headers = { "X-Admin-Token": adminToken };
      const [sourcesRes, outcomesRes] = await Promise.all([
        fetch(`${API_BASE}/admin/sources`, { headers }),
        fetch(`${API_BASE}/admin/outcomes`, { headers }),
      ]);
      if (sourcesRes.ok) {
        const sourceData = await sourcesRes.json();
        setSources(Array.isArray(sourceData) ? sourceData : []);
      }
      if (outcomesRes.ok) {
        const outcomeData = await outcomesRes.json();
        setOutcomes(Array.isArray(outcomeData) ? outcomeData : []);
      }
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

      {sources.length > 0 && (
        <section className="max-w-5xl mx-auto mt-16">
          <h2 className="text-2xl font-medium tracking-tight">Source Scoreboard</h2>
          <p className="text-sm text-gray-500 mt-1 mb-4">
            Incrementality per source: a high never-seen rate with a low 7-day growth ratio means
            we surfaced something the internet wasn&apos;t going to deliver. Growth ≥3x = we frontran a blowup.
          </p>
          <div className="overflow-x-auto border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <th className="p-3">Source</th>
                  <th className="p-3">Type</th>
                  <th className="p-3 text-right">Candidates</th>
                  <th className="p-3 text-right">Rejected</th>
                  <th className="p-3 text-right">Avg Diamond</th>
                  <th className="p-3 text-right">Featured</th>
                  <th className="p-3 text-right">Never-Seen %</th>
                  <th className="p-3 text-right">Avg 7d Growth</th>
                  <th className="p-3 text-right">Blowups (≥3x)</th>
                </tr>
              </thead>
              <tbody>
                {sources.map(s => (
                  <tr key={`${s.creator_name}|${s.source_type}`} className="border-b border-gray-100">
                    <td className="p-3 font-medium">{s.creator_name}</td>
                    <td className="p-3 text-gray-500">{s.source_type}</td>
                    <td className="p-3 text-right">{s.candidates}</td>
                    <td className="p-3 text-right">{s.rejected}</td>
                    <td className="p-3 text-right">{s.avg_diamond ?? "–"}</td>
                    <td className="p-3 text-right">{s.picks_featured}</td>
                    <td className="p-3 text-right">{s.never_seen_rate != null ? `${Math.round(s.never_seen_rate * 100)}%` : "–"}</td>
                    <td className="p-3 text-right">{s.avg_growth_ratio != null ? `${s.avg_growth_ratio}x` : "–"}</td>
                    <td className="p-3 text-right">{s.outcomes_checked > 0 ? `${s.blowups}/${s.outcomes_checked}` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {outcomes.length > 0 && (
        <section className="max-w-5xl mx-auto mt-16">
          <h2 className="text-2xl font-medium tracking-tight">Pick Outcomes</h2>
          <p className="text-sm text-gray-500 mt-1 mb-4">
            Score breakdown vs. 7-day view delta per featured pick — the raw data for tuning
            the Diamond Score weights. Growth fills in once each pick passes the 7-day check.
          </p>
          <div className="overflow-x-auto border border-gray-200 bg-white">
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <th className="p-3">Featured</th>
                  <th className="p-3">Title</th>
                  <th className="p-3 text-right">Views@Feature</th>
                  <th className="p-3 text-right">Views+7d</th>
                  <th className="p-3 text-right">Growth</th>
                  <th className="p-3 text-right">Never/Knew</th>
                  <th className="p-3 text-right">Dia</th>
                  <th className="p-3 text-right">Qua</th>
                  <th className="p-3 text-right">Int</th>
                  <th className="p-3 text-right">Rar</th>
                  <th className="p-3 text-right">Ori</th>
                  <th className="p-3 text-right">Out</th>
                  <th className="p-3 text-right">Clk</th>
                </tr>
              </thead>
              <tbody>
                {outcomes.map(o => (
                  <tr key={o.hourly_id} className="border-b border-gray-100">
                    <td className="p-3 text-gray-500">{o.publish_time.split(".")[0]}</td>
                    <td className="p-3 font-medium max-w-xs overflow-hidden text-ellipsis" title={o.title ?? undefined}>
                      {o.title || "(removed)"}
                    </td>
                    <td className="p-3 text-right">{compact(o.views_at_feature)}</td>
                    <td className="p-3 text-right">{compact(o.views_after_7d)}</td>
                    <td className="p-3 text-right font-bold">{o.growth_ratio != null ? `${o.growth_ratio}x` : "–"}</td>
                    <td className="p-3 text-right">{o.never_seen}/{o.knew_already}</td>
                    <td className="p-3 text-right font-bold">{num(o.diamond_score)}</td>
                    <td className="p-3 text-right">{num(o.quality_score)}</td>
                    <td className="p-3 text-right">{num(o.interestingness_score)}</td>
                    <td className="p-3 text-right">{num(o.rarity_score)}</td>
                    <td className="p-3 text-right">{num(o.originality_score)}</td>
                    <td className="p-3 text-right">{num(o.outlier_score)}</td>
                    <td className="p-3 text-right">{num(o.clickbait_penalty)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
