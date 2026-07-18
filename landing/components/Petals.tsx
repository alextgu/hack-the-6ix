/** Ambient sakura petals drifting down a section. Server component — the
 *  values are deterministic (no Math.random), so SSR and client agree.
 *  Hidden entirely under prefers-reduced-motion (see globals.css). */

const PETALS = [
  { left: "4%", size: 14, duration: 17, delay: 0, drift: 0.9, spin: 1, opacity: 0.4 },
  { left: "12%", size: 10, duration: 21, delay: 4.5, drift: 1.2, spin: -1, opacity: 0.3 },
  { left: "22%", size: 16, duration: 15, delay: 8, drift: 0.7, spin: 1.4, opacity: 0.45 },
  { left: "31%", size: 9, duration: 23, delay: 2, drift: 1.4, spin: -0.8, opacity: 0.25 },
  { left: "43%", size: 13, duration: 18, delay: 11, drift: 1.0, spin: 1.1, opacity: 0.4 },
  { left: "55%", size: 11, duration: 20, delay: 6, drift: 0.8, spin: -1.2, opacity: 0.3 },
  { left: "64%", size: 15, duration: 16, delay: 13, drift: 1.1, spin: 0.9, opacity: 0.45 },
  { left: "73%", size: 9, duration: 24, delay: 1, drift: 1.3, spin: -1, opacity: 0.25 },
  { left: "82%", size: 12, duration: 19, delay: 9, drift: 0.9, spin: 1.3, opacity: 0.35 },
  { left: "91%", size: 14, duration: 17, delay: 5, drift: 1.15, spin: -0.9, opacity: 0.4 },
  { left: "37%", size: 8, duration: 26, delay: 15, drift: 1.5, spin: 1, opacity: 0.2 },
  { left: "68%", size: 10, duration: 22, delay: 3, drift: 0.75, spin: -1.4, opacity: 0.3 },
];

export default function Petals() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {PETALS.map((p, i) => (
        <span
          key={i}
          className="petal"
          style={
            {
              left: p.left,
              fontSize: `${p.size}px`,
              "--petal-duration": `${p.duration}s`,
              "--petal-delay": `${p.delay}s`,
              "--petal-drift": p.drift,
              "--petal-spin": p.spin,
              "--petal-opacity": p.opacity,
            } as React.CSSProperties
          }
        >
          🌸
        </span>
      ))}
    </div>
  );
}
