"use client";

import { useEffect, useState } from 'react';

/** Parse the API's naive-UTC ISO strings ("2026-09-10T10:00:00") as UTC. */
function toMs(iso: string): number {
  return Date.parse(iso.replace(" ", "T").split(".")[0] + "Z");
}

function format(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes > 0) return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
  return `${seconds}s`;
}

/**
 * Time remaining until the next pick goes live.
 *
 * With four picks a day the wait is long enough to be worth showing, and it
 * turns the schedule into something a reader can plan around. `onElapsed` fires
 * once when the slot turns over, so the page can fetch the new pick immediately
 * instead of waiting for its next poll -- pass a stable callback, or it will
 * fire again on every render until fresh data arrives.
 */
export default function Countdown({
  target,
  onElapsed,
}: {
  target: string;
  onElapsed?: () => void;
}) {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    // Ticks arrive from timer callbacks, never synchronously in the effect body.
    const tick = () => setNow(Date.now());
    const first = window.setTimeout(tick, 0);
    const every = window.setInterval(tick, 1000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(every);
    };
  }, []);

  const targetMs = toMs(target);
  const remaining = now === null || Number.isNaN(targetMs) ? null : targetMs - now;
  const elapsed = remaining !== null && remaining <= 0;

  useEffect(() => {
    if (elapsed && onElapsed) onElapsed();
  }, [elapsed, onElapsed]);

  if (remaining === null) return <span>&hellip;</span>;
  if (elapsed) return <span>a moment</span>;
  return (
    // aria-live off: a per-second change would otherwise be announced constantly
    <time dateTime={new Date(targetMs).toISOString()} aria-live="off">
      {format(remaining)}
    </time>
  );
}
