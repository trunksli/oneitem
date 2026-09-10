"use client";

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { API_BASE } from '@/lib/api';
import ApiWarning from '@/components/api-warning';
import Thumbnail from '@/components/thumbnail';
import { useSessionState } from '@/lib/use-persistent-state';

interface QueueCandidate {
  id: string;
  title: string;
  creator_name: string;
  url: string;
  source_type: string;
  theme: string | null;
  tone: string | null;
  preview_text: string | null;
  thumbnail_url: string | null;
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

interface Slot {
  publish_time: string;
  is_current_hour: boolean;
  hourly_id: string | null;
  theme: string | null;
  candidate_id: string | null;
  title: string | null;
  creator_name: string | null;
  thumbnail_url: string | null;
  source_type: string | null;
  diamond_score: number | null;
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

function num(value: number | null): string {
  return value == null ? "–" : String(Math.round(value));
}

function hourLabel(iso: string): string {
  const date = new Date(iso.replace(" ", "T").split(".")[0] + "Z");
  if (isNaN(date.getTime())) return iso;
  return date.toLocaleString('en-US', { weekday: 'short', hour: 'numeric' });
}

const SESSION_KEY = "one_admin_session";

const cell = { padding: '10px 12px', borderBottom: '1px solid var(--line)' } as const;
const headCell = { padding: '10px 12px', borderBottom: '1px solid var(--line-strong)', textAlign: 'left' as const };

export default function Admin() {
  // Session token lives in sessionStorage, not localStorage: it dies with the tab
  // and expires server-side, so a copied browser profile does not grant access.
  const [token, setToken] = useSessionState(SESSION_KEY);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const [queue, setQueue] = useState<QueueCandidate[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [sources, setSources] = useState<SourceStats[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [targetHour, setTargetHour] = useState<Record<string, string>>({});

  const loadAll = useCallback(async (sessionToken: string) => {
    // No setState before the first await: this runs from an effect, and a
    // synchronous update there would cascade an extra render.
    try {
      const headers = { "X-Admin-Token": sessionToken };
      const [queueRes, scheduleRes, sourcesRes] = await Promise.all([
        fetch(`${API_BASE}/admin/queue?limit=25`, { headers }),
        fetch(`${API_BASE}/admin/schedule?hours=24`, { headers }),
        fetch(`${API_BASE}/admin/sources`, { headers }),
      ]);

      if (queueRes.status === 403) {
        // Session expired or revoked; drop it and show the login form again.
        setToken("");
        setLoginError("Your session expired. Please sign in again.");
        return;
      }

      const queueData = await queueRes.json();
      setQueue(Array.isArray(queueData) ? queueData : []);
      if (scheduleRes.ok) {
        const s = await scheduleRes.json();
        setSlots(Array.isArray(s) ? s : []);
      }
      if (sourcesRes.ok) {
        const s = await sourcesRes.json();
        setSources(Array.isArray(s) ? s : []);
      }
      setLoadFailed(false);
      setStatus(`${Array.isArray(queueData) ? queueData.length : 0} candidates awaiting review.`);
    } catch (err) {
      console.error(err);
      setLoadFailed(true);
      setStatus("Could not reach the API.");
    }
  }, [setToken]);   // setToken is stable (see use-persistent-state)

  // Keyed on the token itself: it only changes on sign-in and sign-out, so this
  // loads exactly once per session without needing a ref to guard re-renders.
  useEffect(() => {
    // Fetching on mount is the canonical use of an effect. The lint rule targets
    // synchronous cascading updates; loadAll only updates state after awaiting
    // the network, so the cascade it guards against cannot happen here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (token) loadAll(token);
  }, [token, loadAll]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    try {
      const res = await fetch(`${API_BASE}/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setLoginError(data.detail || "Sign in failed.");
        return;
      }
      setToken(data.token);   // the effect above loads once the token lands
      setPassword("");
    } catch (err) {
      console.error(err);
      setLoginError("Could not reach the API.");
    }
  };

  const signOut = () => {
    setToken("");
    setQueue([]);
    setSlots([]);
  };

  const post = async (path: string, body: Record<string, unknown>, okMessage: string) => {
    if (busy || !token) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/admin/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setStatus(res.ok ? okMessage : `Error: ${data.detail || res.status}`);
      if (res.ok) await loadAll(token);
    } catch (err) {
      console.error(err);
      setStatus("Request failed.");
    } finally {
      setBusy(false);
    }
  };

  const openSlots = slots.filter(s => !s.hourly_id);

  // ------------------------------------------------------------------ login
  if (!token) {
    return (
      <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
        <ApiWarning failed={loadFailed} />
        <header className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
                style={{ borderBottom: '2px solid var(--rule)' }}>
          <Link href="/" className="display text-2xl font-bold tracking-tight leading-none"
                style={{ color: 'var(--ink)', textDecoration: 'none' }}>ONE</Link>
          <Link href="/" className="label link-accent">Now Playing &#8594;</Link>
        </header>

        <div className="mx-auto px-6 py-16" style={{ maxWidth: 380 }}>
          <p className="label" style={{ color: 'var(--ink-faint)' }}>Curation</p>
          <h1 className="display mt-3 text-3xl">Sign in</h1>
          <form onSubmit={handleLogin} className="mt-6 flex flex-col gap-3">
            <input
              type="text" value={username} autoComplete="username"
              onChange={(e) => setUsername(e.target.value)} placeholder="Username"
              className="px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--surface)', color: 'var(--ink)',
                       border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm)' }}
            />
            <input
              type="password" value={password} autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)} placeholder="Password"
              className="px-3 py-2 text-sm outline-none"
              style={{ background: 'var(--surface)', color: 'var(--ink)',
                       border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm)' }}
            />
            <button type="submit" className="btn btn-primary">Sign in</button>
          </form>
          {loginError && (
            <p className="text-sm mt-4" style={{ color: 'var(--danger)' }}>{loginError}</p>
          )}
        </div>
      </main>
    );
  }

  // ----------------------------------------------------------------- console
  return (
    <main className="min-h-screen" style={{ background: 'var(--paper)', color: 'var(--ink)' }}>
      <ApiWarning failed={loadFailed} />

      <header className="w-full flex justify-between items-center gap-4 px-6 md:px-10 py-4"
              style={{ borderBottom: '2px solid var(--rule)' }}>
        <Link href="/" className="display text-2xl font-bold tracking-tight leading-none"
              style={{ color: 'var(--ink)', textDecoration: 'none' }}>ONE</Link>
        <div className="flex items-center gap-5">
          <Link href="/" className="label link-accent">Now Playing &#8594;</Link>
          <button onClick={signOut} className="label link-accent"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
            Sign out
          </button>
        </div>
      </header>

      <div className="mx-auto px-6 md:px-10 py-10" style={{ maxWidth: 1100 }}>
        <p className="label" style={{ color: 'var(--ink-faint)' }}>Curation</p>
        <h1 className="display mt-3 text-3xl md:text-4xl">The next 24 hours</h1>
        <p className="mt-2 text-[15px]" style={{ color: 'var(--ink-muted)' }}>{status}</p>

        {/* Runway */}
        <section className="mt-8">
          <div className="overflow-x-auto" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
            <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr className="label" style={{ color: 'var(--ink-faint)' }}>
                  <th style={headCell}>Hour</th>
                  <th style={headCell}>Scheduled</th>
                  <th style={headCell}>Theme</th>
                  <th style={{ ...headCell, textAlign: 'right' }}>Score</th>
                  <th style={{ ...headCell, textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {slots.map(slot => (
                  <tr key={slot.publish_time}
                      style={slot.is_current_hour ? { background: 'var(--accent-wash)' } : undefined}>
                    <td style={{ ...cell, whiteSpace: 'nowrap' }}>
                      {hourLabel(slot.publish_time)}
                      {slot.is_current_hour && (
                        <span className="label ml-2" style={{ color: 'var(--accent)' }}>live</span>
                      )}
                    </td>
                    <td style={{ ...cell, fontWeight: slot.title ? 600 : 400,
                                 color: slot.title ? 'var(--ink)' : 'var(--ink-faint)' }}>
                      {slot.title || "— empty, the algorithm will choose —"}
                      {slot.creator_name && (
                        <span style={{ color: 'var(--ink-muted)', fontWeight: 400 }}> / {slot.creator_name}</span>
                      )}
                    </td>
                    <td style={{ ...cell, color: 'var(--ink-muted)' }}>{slot.theme || "–"}</td>
                    <td style={{ ...cell, textAlign: 'right' }}>{num(slot.diamond_score)}</td>
                    <td style={{ ...cell, textAlign: 'right' }}>
                      {slot.hourly_id && !slot.is_current_hour && (
                        <button
                          onClick={() => post("unschedule", { hourly_id: slot.hourly_id }, "Slot cleared.")}
                          disabled={busy}
                          className="label link-accent"
                          style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                        >
                          Clear
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Queue */}
        <h2 className="display text-2xl mt-16">Review queue</h2>
        <p className="mt-2 mb-5 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
          Ranked by Diamond Score. Assign one to an upcoming hour, or reject it.
        </p>

        <div className="flex flex-col gap-4">
          {queue.map((c, rank) => (
            <div key={c.id} className="p-5 flex gap-5" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <Thumbnail
                src={c.thumbnail_url}
                alt=""
                className="w-32 h-[72px] shrink-0 hidden sm:block"
                style={{ border: '1px solid var(--line)' }}
                fallback={
                  <div className="h-full flex items-center justify-center">
                    <span className="label" style={{ color: 'var(--accent)' }}>{c.tone || "Text"}</span>
                  </div>
                }
              />

              <div className="min-w-0 flex-1">
                <p className="label" style={{ color: 'var(--accent)' }}>
                  #{rank + 1} / {c.source_type} / {c.theme || "?"}{c.tone ? ` / ${c.tone}` : ""}
                </p>
                <a href={c.url} target="_blank" rel="noopener noreferrer"
                   className="display text-lg leading-snug" style={{ color: 'var(--ink)', textDecoration: 'none' }}>
                  {c.title}
                </a>
                <p className="text-sm mt-1" style={{ color: 'var(--ink-muted)' }}>{c.creator_name}</p>

                {c.preview_text && (
                  <p className="text-[15px] mt-2 leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
                    {c.preview_text.slice(0, 240)}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs" style={{ color: 'var(--ink-muted)' }}>
                  <span style={{ color: 'var(--accent)', fontWeight: 700 }}>Diamond {num(c.diamond_score)}</span>
                  <span>Quality {num(c.quality_score)}</span>
                  <span>Interest {num(c.interestingness_score)}</span>
                  <span>Rarity {num(c.rarity_score)}</span>
                  <span>Original {num(c.originality_score)}</span>
                  <span>Outlier +{num(c.outlier_score)}</span>
                  <span>Clickbait {num(c.clickbait_penalty)}</span>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <select
                    value={targetHour[c.id] || ""}
                    onChange={(e) => setTargetHour({ ...targetHour, [c.id]: e.target.value })}
                    className="px-2 py-2 text-sm outline-none"
                    style={{ background: 'var(--paper)', color: 'var(--ink)',
                             border: '1px solid var(--line-strong)', borderRadius: 'var(--radius-sm)' }}
                  >
                    <option value="">Now (this hour)</option>
                    {openSlots.filter(s => !s.is_current_hour).map(s => (
                      <option key={s.publish_time} value={s.publish_time}>{hourLabel(s.publish_time)}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => post("schedule",
                      targetHour[c.id]
                        ? { candidate_id: c.id, publish_time: targetHour[c.id] }
                        : { candidate_id: c.id },
                      "Scheduled.")}
                    disabled={busy}
                    className="btn btn-primary"
                    style={{ minHeight: 40, padding: '8px 18px', fontSize: 12 }}
                  >
                    Schedule
                  </button>
                  <button
                    onClick={() => post("reject", { candidate_id: c.id }, "Rejected.")}
                    disabled={busy}
                    className="btn btn-secondary"
                    style={{ minHeight: 40, padding: '8px 18px', fontSize: 12 }}
                  >
                    Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Source scoreboard */}
        {sources.length > 0 && (
          <section className="mt-16 mb-16">
            <h2 className="display text-2xl">Source scoreboard</h2>
            <p className="mt-2 mb-5 text-[15px]" style={{ color: 'var(--ink-muted)' }}>
              A high new-to-me rate with low 7-day growth means we surfaced something the
              internet was not going to deliver on its own.
            </p>
            <div className="overflow-x-auto" style={{ background: 'var(--surface)', border: '1px solid var(--line)' }}>
              <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr className="label" style={{ color: 'var(--ink-faint)' }}>
                    <th style={headCell}>Source</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Cands</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Avg Diamond</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Featured</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>New-to-me</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Avg 7d</th>
                    <th style={{ ...headCell, textAlign: 'right' }}>Blowups</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map(s => (
                    <tr key={`${s.creator_name}|${s.source_type}`}>
                      <td style={{ ...cell, fontWeight: 600 }}>{s.creator_name}</td>
                      <td style={{ ...cell, textAlign: 'right' }}>{s.candidates}</td>
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
      </div>
    </main>
  );
}
