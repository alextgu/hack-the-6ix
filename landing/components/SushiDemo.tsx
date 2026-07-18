"use client";

import { useMemo, useState } from "react";
import {
  MAX_WEEK,
  MOOD_COLOR,
  MOOD_SUSHI_STYLE,
  PHYSICAL_COLOR,
  MENTAL_COLOR,
  committedState,
  stateAtWeek,
} from "@/lib/petModel";

function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs" style={{ color: "var(--ink-dim)" }}>
        <span>{label}</span>
        <span className="tabular-nums font-medium" style={{ color: "var(--ink)" }}>
          {value}%
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.07)" }}>
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${value}%`,
            background: `linear-gradient(90deg, ${color}88, ${color})`,
            boxShadow: `0 0 12px ${color}55`,
          }}
        />
      </div>
    </div>
  );
}

/* Sparkle burst shown once on graduation. */
const SPARKS = [
  { x: -70, y: -50, delay: 0 },
  { x: 70, y: -55, delay: 0.08 },
  { x: -45, y: -85, delay: 0.16 },
  { x: 45, y: -80, delay: 0.05 },
  { x: 0, y: -95, delay: 0.12 },
  { x: -85, y: -10, delay: 0.2 },
  { x: 85, y: -15, delay: 0.14 },
];

export default function SushiDemo() {
  const [week, setWeek] = useState(0);
  const [booked, setBooked] = useState(false);

  const pet = useMemo(() => (booked ? committedState() : stateAtWeek(week)), [week, booked]);
  const sushi = MOOD_SUSHI_STYLE[pet.mood];
  const glow = MOOD_COLOR[pet.mood];

  return (
    <div
      className="mx-auto w-full max-w-md rounded-3xl border p-6 shadow-2xl backdrop-blur-sm sm:p-7"
      style={{
        borderColor: "rgba(246,198,208,0.16)",
        background: "linear-gradient(180deg, rgba(35,36,65,0.85), rgba(18,19,31,0.95))",
      }}
    >
      {/* Stage */}
      <div
        className="relative mb-5 flex h-60 items-center justify-center overflow-hidden rounded-2xl transition-shadow duration-700"
        style={{
          background: "radial-gradient(ellipse at 50% 70%, rgba(255,255,255,0.05), transparent 65%), var(--night-soft)",
          boxShadow: `inset 0 0 90px ${glow}2e`,
        }}
      >
        {/* mood glow floor */}
        <div
          aria-hidden
          className="absolute bottom-6 h-8 w-40 rounded-full transition-all duration-700"
          style={{ background: glow, opacity: 0.18, filter: "blur(22px)" }}
        />

        {/* ART SLOT — placeholder 🍣. Swap this <span> for a Lottie animation
            keyed on `pet.mood` when the designer's Sushi-kun art lands. */}
        <span
          key={booked ? "booked" : "alive"}
          className={`select-none text-8xl transition-all duration-500 ${
            booked ? "animate-pop" : pet.mood === "dying" ? "" : "animate-floaty"
          }`}
          style={{
            filter: sushi.filter,
            transform: sushi.transform,
            opacity: sushi.opacity,
            transitionTimingFunction: "cubic-bezier(0.22, 1.2, 0.36, 1)",
          }}
          role="img"
          aria-label={`Sushi-kun looking ${pet.mood}`}
        >
          🍣
        </span>

        {/* graduation sparkles */}
        {booked && (
          <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
            {SPARKS.map((s, i) => (
              <span
                key={i}
                className="animate-sparkle absolute text-xl"
                style={
                  {
                    "--spark-x": `${s.x}px`,
                    "--spark-y": `${s.y}px`,
                    "--spark-delay": `${s.delay}s`,
                  } as React.CSSProperties
                }
              >
                ✨
              </span>
            ))}
          </div>
        )}

        <span
          className="absolute right-3 top-3 rounded-full px-2.5 py-1 text-xs font-medium tracking-wide transition-colors duration-500"
          style={{ backgroundColor: `${glow}1f`, color: glow, border: `1px solid ${glow}44` }}
        >
          {pet.mood}
        </span>
      </div>

      {/* Dialogue */}
      <p
        className="font-display mb-5 min-h-[1.75rem] text-center text-[15px] italic transition-opacity duration-300"
        style={{ color: "var(--sakura)" }}
      >
        「{pet.caption}」
      </p>

      {/* Market ticker — 時価 */}
      <div className="mb-5 flex items-stretch gap-3">
        <div
          className="flex-1 rounded-xl border px-3.5 py-2.5"
          style={{ borderColor: "rgba(245,165,36,0.25)", background: "rgba(245,165,36,0.06)" }}
        >
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--amber)" }}>
            時価 · market price
          </div>
          <div className="tabular-nums text-lg font-semibold transition-all duration-300" style={{ color: "var(--paper)" }}>
            ${pet.price}
            <span className="ml-1 text-xs font-normal" style={{ color: "var(--ink-dim)" }}>
              / night
            </span>
          </div>
        </div>
        <div
          className="flex-1 rounded-xl border px-3.5 py-2.5"
          style={{ borderColor: "rgba(246,198,208,0.2)", background: "rgba(246,198,208,0.05)" }}
        >
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--sakura-deep)" }}>
            rooms left
          </div>
          <div className="tabular-nums text-lg font-semibold transition-all duration-300" style={{ color: "var(--paper)" }}>
            {pet.rooms}
          </div>
        </div>
      </div>

      {/* Health bars */}
      <div className="mb-6 space-y-3.5">
        <Bar label="Physical (booking pressure)" value={pet.physical} color={PHYSICAL_COLOR} />
        <Bar label="Mental (group vibe)" value={pet.mental} color={MENTAL_COLOR} />
      </div>

      {/* Week slider 0–6 */}
      <div className="mb-5">
        <div className="mb-2.5 flex items-center justify-between text-xs" style={{ color: "var(--ink-dim)" }}>
          <span>drag to procrastinate →</span>
          <span className="tabular-nums font-medium" style={{ color: "var(--ink)" }}>
            week {booked ? "—" : pet.week}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={MAX_WEEK}
          step={1}
          value={week}
          onChange={(e) => {
            setBooked(false); // dragging un-books him
            setWeek(Number(e.target.value));
          }}
          className="scrubber w-full"
          aria-label="Weeks of procrastination"
        />
      </div>

      {/* Revive */}
      <button
        type="button"
        onClick={() => setBooked(true)}
        disabled={booked}
        className="cta-glow w-full rounded-2xl px-4 py-3.5 text-sm font-semibold disabled:cursor-default"
        style={{
          background: booked
            ? "linear-gradient(90deg, #7CD992, #5cbf78)"
            : "linear-gradient(90deg, var(--amber), var(--amber-deep))",
          color: "var(--night)",
        }}
      >
        {booked ? "🎉 booked — Sushi-kun is free" : "Book it → revive Sushi-kun"}
      </button>
    </div>
  );
}
