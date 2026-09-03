"use client";

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { API_BASE } from '@/lib/api';
import ApiWarning from '@/components/api-warning';
import { usePersistentState } from '@/lib/use-persistent-state';


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

const cell = { padding: '10px 12px', borderBottom: '1px solid var(--line)' } as const;
const headCell = { padding: '10px 12px', borderBottom: '1px solid var(--line-strong)', textAlign: 'left' as const };

export default function Admin() {
  const [token, setToken] = usePersistentState("one_admin_token");
  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [sources, setSources] = useState<SourceStats[]>([]);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [status, setStatus] = useState("Enter the admin token to load the queue.");
  const [busy, setBusy] = useState(false);

  const loadQueue = useCallback(async (adminToken: string) => {
    if (!adminToken) return;
    setStatus("Loading queue...");
    try {
      const headers = { "X-Admin-Token": adminToken };
      const res = await fetch(`${API_BASE}/admin/queue?limit=15`, { headers });
      if (res.status === 403) {
        setStatus("Invalid admin token.");
        setQueue([]);
        return;
      }
      const data = await res.json();
      setQueue(Array.isArray(data) ? data : []);
      setStatus(`${Array.isArray(data) ? data.length : 0} candidates pending review, ranked by Diamond Score.`);

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

  // Load once on mount if a token was already stored; the ref keeps typing in the
  // token field from re-triggering a fetch on every keystroke.
  const loadedOnce = useRef(false);
  useEffect(() => {
    if (loadedOnce.current || !token) return;
    loadedOnce.current = true;
    loadQueue(token);
  }, [token, loadQueue]);

  const handleTokenSubmit = (e: React.FormEvent) => {
    e.preventDefault();
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
          ? "Featured for the current hour. Any displaced pick is back in the queue."
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
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
      <ApiWarning />


      <header
        className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
        style={{ borderBottom: '2px solid var(--rule)' }}
      >
        <Link href="/" className="display text-2xl font-bold tracking-tight leading-none" style={{ color: 'var(--ink)', textDecoration: 'none' }}>
          ONE
        </Link>
        <Link href="/" className="label link-accent">Now Playing &#8594;</Link>
      </header>

      <div className="mx-auto px-6 md:px-10 py-10" style={{ maxWidth: 1100 }}>
        <p className="label" style={{ color: 'var(--ink-faint)' }}>Curation</p>
        <h1 className="display mt-3 text-3xl md:text-4xl">Review Queue</h1>
        <p className="mt-2 text-[15px]" style={{ color: 'var(--ink-muted)' }}>{status}</p>

        <form onSubmit={handleTokenSubmit} className="mt-5 flex gap-2 max-w-md">
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Admin token"
            className="flex-1 px-3 py-2 text-sm outline-none"
            style={{
              background: 'var(--surface)', color: 'var(--ink)',
              border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm)',
            }}
          />
          <button type="submit" className="btn btn-primary" style={{ minHeight: 40, padding: '8px 20px' }}>
            Load
          </button>
        </form>

        {/* Queue */}
        <div className="mt-10 flex flex-col gap-4">
          {queue.map((c, rank) => (
            <div key={c.id} className="p-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <div className="flex flex-wrap justify-between items-start gap-4">
                <div className="min-w-0">
                  <p className="label" style={{ color: 'var(--accent)' }}>
                    #{rank + 1} / {c.source_type} / {(c.theme || "?").replace(/_/g, " ")}
                  </p>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="display text-lg leading-snug"
                    style={{ color: 'var(--ink)', textDecoration: 'none' }}
                  >
                    {c.title}
                  </a>
                  <p className="text-sm mt-1" style={{ color: 'var(--ink-muted)' }}>
                    {c.creator_name}
                    {c.view_count != null && <> / {c.view_count.toLocaleString()} views</>}
                    {c.subscriber_count != null && c.subscriber_count > 0 && <> of {c.subscriber_count.toLocaleString()} subs</>}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => act("schedule", c.id)}
                    disabled={busy}
                    className="btn btn-primary"
                    style={{ minHeight: 40, padding: '8px 18px', fontSize: 12 }}
                  >
                    Feature Now
                  </button>
                  <button
                    onClick={() => act("reject", c.id)}
                    disabled={busy}
                    className="btn btn-secondary"
                    style={{ minHeight: 40, padding: '8px 18px', fontSize: 12 }}
                  >
                    Reject
                  </button>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs" style={{ color: 'var(--ink-muted)' }}>
                <span style={{ color: 'var(--accent)', fontWeight: 700 }}>Diamond {num(c.diamond_score)}</span>
                <span>Quality {num(c.quality_score)}</span>
                <span>Interest {num(c.interestingness_score)}</span>
                <span>Rarity {num(c.rarity_score)}</span>
                <span>Original {num(c.originality_score)}</span>
                <span>Outlier +{num(c.outlier_score)}</span>
                <span>Clickbait {num(c.clickbait_penalty)}</span>
                <span>Trust {num(c.trustworthiness_score)}</span>
              </div>

              {c.ai_explanation && (
                <p className="display text-[15px] mt-3 leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
                  {c.ai_explanation}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Source scoreboard */}
        {sources.length > 0 && (
          <section className="mt-16">
            <h2 className="display text-2xl">Source Scoreboard</h2>
            <p className="mt-2 mb-5 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
              A high never-seen rate with low 7-day growth means we surfaced something the
              internet was not going to deliver on its own. Growth of 3x or more means we
              front-ran a blowup.
            </p>
            <div className="overflow-x-auto" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="label" style={{ color: 'var(--ink-faint)' }}>
                    <th style={headCell}>Source</th>
                    <th style={headCell}>Type</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Cands</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Rej</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Avg Diamond</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Featured</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Never-Seen</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Avg 7d</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Blowups</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map(s => (
                    <tr key={`${s.creator_name}|${s.source_type}`}>
                      <td style={{ ...cell, fontWeight: 600 }}>{s.creator_name}</td>
                      <td style={{ ...cell, color: 'var(--ink-muted)' }}>{s.source_type}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{s.candidates}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{s.rejected}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{s.avg_diamond ?? "–"}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{s.picks_featured}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>
                        {s.never_seen_rate != null ? `${Math.round(s.never_seen_rate * 100)}%` : "–"}
                      </td>
                      <td style={{ ...cell, textAlign: 'right' }}>
                        {s.avg_growth_ratio != null ? `${s.avg_growth_ratio}x` : "–"}
                      </td>
                      <td style={{ ...cell, textAlign: 'right' }}>
                        {s.outcomes_checked > 0 ? `${s.blowups}/${s.outcomes_checked}` : "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Outcomes */}
        {outcomes.length > 0 && (
          <section className="mt-16 mb-16">
            <h2 className="display text-2xl">Pick Outcomes</h2>
            <p className="mt-2 mb-5 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
              Score breakdown against the 7-day view delta for every featured pick &mdash;
              the raw data for tuning the Diamond Score weights.
            </p>
            <div className="overflow-x-auto" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <table className="w-full text-sm whitespace-nowrap" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="label" style={{ color: 'var(--ink-faint)' }}>
                    <th style={headCell}>Featured</th>
                    <th style={headCell}>Title</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Views@</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>+7d</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Growth</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>N/K</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Dia</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Qua</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Int</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Rar</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Ori</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Out</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Clk</th>
                  </tr>
                </thead>
                <tbody>
                  {outcomes.map(o => (
                    <tr key={o.hourly_id}>
                      <td style={{ ...cell, color: 'var(--ink-muted)' }}>{o.publish_time.split(".")[0].replace("T", " ")}</td>
                      <td style={{ ...cell, fontWeight: 600, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }} title={o.title ?? undefined}>
                        {o.title || "(removed)"}
                      </td>
                      <td style={{ ...cell, textAlign: 'right' }}>{compact(o.views_at_feature)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{compact(o.views_after_7d)}</td>
                      <td style={{ ...cell, textAlign: 'right', fontWeight: 700, color: 'var(--accent)' }}>
                        {o.growth_ratio != null ? `${o.growth_ratio}x` : "–"}
                      </td>
                      <td style={{ ...cell, textAlign: 'right' }}>{o.never_seen}/{o.knew_already}</td>
                      <td style={{ ...cell, textAlign: 'right', fontWeight: 700 }}>{num(o.diamond_score)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{num(o.quality_score)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{num(o.interestingness_score)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{num(o.rarity_score)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{num(o.originality_score)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{num(o.outlier_score)}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{num(o.clickbait_penalty)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
