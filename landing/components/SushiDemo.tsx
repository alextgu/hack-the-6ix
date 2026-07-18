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
      <div className="mb-1 flex items-center justify-between text-xs text-neutral-400">
        <span>{label}</span>
        <span className="tabular-nums text-neutral-200">{value}%</span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-neutral-800">
        <div
          className="h-full rounded-full transition-all duration-300 ease-out"
          style={{ width: `${value}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export default function SushiDemo() {
  const [week, setWeek] = useState(0);
  const [booked, setBooked] = useState(false);

  const pet = useMemo(() => (booked ? committedState() : stateAtWeek(week)), [week, booked]);
  const sushi = MOOD_SUSHI_STYLE[pet.mood];
  const glow = MOOD_COLOR[pet.mood];

  return (
    <div className="mx-auto w-full max-w-md rounded-2xl border border-neutral-800 bg-neutral-950 p-6 shadow-2xl">
      {/* Stage */}
      <div
        className="relative mb-5 flex h-56 items-center justify-center rounded-xl bg-neutral-900"
        style={{ boxShadow: `inset 0 0 80px ${glow}22` }}
      >
        {/* ART SLOT — placeholder 🍣. Swap this <span> for a Lottie animation
            keyed on `pet.mood` when the designer's Sushi-kun art lands. */}
        <span
          className="select-none text-8xl transition-all duration-300 ease-out"
          style={{
            filter: sushi.filter,
            transform: sushi.transform,
            opacity: sushi.opacity,
          }}
          role="img"
          aria-label={`Sushi-kun looking ${pet.mood}`}
        >
          🍣
        </span>
        <span
          className="absolute right-3 top-3 rounded-full px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: `${glow}22`, color: glow }}
        >
          {pet.mood}
        </span>
      </div>

      {/* Dialogue */}
      <p className="mb-5 min-h-[1.5rem] text-center text-sm italic text-neutral-300">
        &ldquo;{pet.caption}&rdquo;
      </p>

      {/* Market ticker — 時価 */}
      <div className="mb-5 flex items-stretch gap-3">
        <div className="flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-neutral-500">
            時価 · market price
          </div>
          <div className="tabular-nums text-lg font-semibold text-neutral-100">
            ${pet.price}
            <span className="ml-1 text-xs font-normal text-neutral-500">/ night</span>
          </div>
        </div>
        <div className="flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2">
          <div className="text-[10px] uppercase tracking-wide text-neutral-500">rooms left</div>
          <div className="tabular-nums text-lg font-semibold text-neutral-100">{pet.rooms}</div>
        </div>
      </div>

      {/* Health bars */}
      <div className="mb-6 space-y-3">
        <Bar label="Physical (booking pressure)" value={pet.physical} color={PHYSICAL_COLOR} />
        <Bar label="Mental (group vibe)" value={pet.mental} color={MENTAL_COLOR} />
      </div>

      {/* Week slider 0–6 */}
      <div className="mb-5">
        <div className="mb-2 flex items-center justify-between text-xs text-neutral-400">
          <span>drag to procrastinate →</span>
          <span className="tabular-nums text-neutral-200">week {booked ? "—" : pet.week}</span>
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
          className="w-full accent-neutral-300"
          aria-label="Weeks of procrastination"
        />
      </div>

      {/* Revive */}
      <button
        type="button"
        onClick={() => setBooked(true)}
        disabled={booked}
        className="w-full rounded-xl bg-amber-400 px-4 py-3 text-sm font-semibold text-neutral-950 transition hover:bg-amber-300 disabled:cursor-default disabled:opacity-60"
      >
        {booked ? "🎉 booked — Sushi-kun is free" : "Book it → revive Sushi-kun"}
      </button>
    </div>
  );
}
