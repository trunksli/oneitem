/**
 * The Curiolet wordmark, in one place so every header carries the same thing.
 *
 * Drawn rather than placed as an image: the logo files have baked-in
 * backgrounds (cream or white) and fixed colours, which would show as a pale
 * block in dark mode and go soft on a retina screen. The star is the logo's own
 * four-point mark as a path, so it takes its colour from the theme tokens and
 * stays sharp at any size. The raster logos live in public/brand for the places
 * that need a file: social profiles, the newsletter, press.
 */
export default function Wordmark({ size = "md" }: { size?: "sm" | "md" }) {
  const type = size === "sm" ? "text-xl" : "text-2xl";
  const star = size === "sm" ? 11 : 13;

  return (
    <span className="inline-flex items-baseline gap-[0.3em] leading-none">
      <svg
        viewBox="0 0 100 100"
        width={star}
        height={star}
        aria-hidden="true"
        focusable="false"
        style={{ color: 'var(--rule)', transform: 'translateY(-0.05em)' }}
      >
        <path
          d="M50 0 Q56 44 100 50 Q56 56 50 100 Q44 56 0 50 Q44 44 50 0 Z"
          fill="currentColor"
        />
      </svg>
      <span className={`display ${type} font-bold tracking-tight leading-none`}>
        Curiolet
      </span>
    </span>
  );
}
